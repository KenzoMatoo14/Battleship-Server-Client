#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <netdb.h>

#define  DIRSIZE   2048      /* longitud maxima parametro entrada/salida */
#define  PUERTO   5000	     /* numero puerto arbitrario */
#define NUM_CELDAS   17

int sd;           /* socket principal del servidor */
int sd_p1 = -1;   /* socket del jugador 1 */
int sd_p2 = -1;   /* socket del jugador 2 */

char usuario_p1[256];
char usuario_p2[256];

#ifndef USUARIOS_FILE
#define USUARIOS_FILE "usuarios.txt"
#endif

/*  procedimiento de aborte del servidor, si llega una senal SIGINT */
/* ( <ctrl> <c> ) se cierra el socket y se aborta el programa       */
void aborta_handler(int sig) {
	printf("\n....abortando el servidor (señal %d)\n", sig);
	if (sd_p1 != -1) close(sd_p1);
	if (sd_p2 != -1) close(sd_p2);
	close(sd);
	exit(1);
}

int recibir_msg(int sock, char* buf, int maxlen) {
	int total = 0;
	char c;
	int n;
	while (total < maxlen - 1) {
		n = recv(sock, &c, 1, 0);
		if (n <= 0) return n;
		if (c == '\n') break;
		buf[total++] = c;
	}
	buf[total] = '\0';
	return total;
}

void enviar_msg(int sock, const char* msg) {
	char buffer[DIRSIZE];
	snprintf(buffer, sizeof(buffer), "%s\n", msg);
	if (send(sock, buffer, strlen(buffer), 0) == -1) {
		perror("send");
		exit(1);
	}
}

/* ─── Utilidades de pipe (texto con \n) ──────────────────────────────────── */
void pipe_escribir(int fd, const char* msg) {
	char buf[DIRSIZE];
	snprintf(buf, sizeof(buf), "%s\n", msg);
	write(fd, buf, strlen(buf));
}

int pipe_leer(int fd, char* buf, int maxlen) {
	int total = 0;
	char c;
	while (total < maxlen - 1) {
		int n = read(fd, &c, 1);
		if (n <= 0) return n;
		if (c == '\n') break;
		buf[total++] = c;
	}
	buf[total] = '\0';
	return total;
}

int parsear_posiciones(const char* raw, char posiciones[][8], int max) {
	char copia[DIRSIZE];
	strncpy(copia, raw, sizeof(copia) - 1);
	copia[sizeof(copia) - 1] = '\0';

	int count = 0;
	char* token = strtok(copia, ",");
	while (token != NULL && count < max) {
		strncpy(posiciones[count], token, 7);
		posiciones[count][7] = '\0';
		count++;
		token = strtok(NULL, ",");
	}
	return count;
}

/* ─── Verificar si una coord está en las posiciones de un jugador ────────── */
int esta_en_posiciones(const char* coord, char posiciones[][8], int num_pos) {
	for (int i = 0; i < num_pos; i++) {
		if (strcmp(posiciones[i], coord) == 0)
			return 1;
	}
	return 0;
}

/* ─── Verificar si todos los barcos fueron hundidos ─────────────────────── */
int todos_hundidos(char posiciones[][8], int num_pos) {
	for (int i = 0; i < num_pos; i++) {
		if (posiciones[i][0] != '\0')   /* posición aún no golpeada */
			return 0;
	}
	return 1;
}

/* Marca una posición como golpeada (vacía el string) */
void marcar_golpeada(const char* coord, char posiciones[][8], int num_pos) {
	for (int i = 0; i < num_pos; i++) {
		if (strcmp(posiciones[i], coord) == 0) {
			posiciones[i][0] = '\0';
			return;
		}
	}
}

/* ══════════════════════════════════════════════════════════════════════════
   AUTENTICACIÓN
   Formato del archivo usuarios.txt:
	 usuario:contraseña
	 usuario2:contraseña2
	 ...
   ══════════════════════════════════════════════════════════════════════════ */

   /* Busca usuario en el archivo. Devuelve 1 si existe, 0 si no.
	  Si existe, copia la contraseña almacenada en pass_out. */
int buscar_usuario(const char* usuario, char* pass_out, int pass_maxlen) {
	FILE* f = fopen(USUARIOS_FILE, "r");
	if (!f) return 0;

	char linea[DIRSIZE];
	while (fgets(linea, sizeof(linea), f)) {
		/* quitar el \n del final */
		linea[strcspn(linea, "\n")] = '\0';

		char* sep = strchr(linea, ':');
		if (!sep) continue;

		*sep = '\0';             /* separa usuario:contraseña */
		char* user_en_archivo = linea;
		char* pass_en_archivo = sep + 1;

		if (strcmp(user_en_archivo, usuario) == 0) {
			strncpy(pass_out, pass_en_archivo, pass_maxlen - 1);
			pass_out[pass_maxlen - 1] = '\0';
			fclose(f);
			return 1;
		}
	}
	fclose(f);
	return 0;
}

/* Agrega un nuevo usuario al archivo. Devuelve 1 si OK, 0 si ya existe. */
int registrar_usuario(const char* usuario, const char* contraseña) {
	char pass_existente[DIRSIZE];
	if (buscar_usuario(usuario, pass_existente, sizeof(pass_existente))) {
		return 0;   /* ya existe */
	}

	FILE* f = fopen(USUARIOS_FILE, "a");
	if (!f) return 0;
	fprintf(f, "%s:%s\n", usuario, contraseña);
	fclose(f);
	return 1;
}

/* Maneja el intercambio de autenticación con un cliente.
   Devuelve 1 si el cliente autenticó correctamente, 0 si falló/desconectó.
   Guarda el nombre de usuario en usuario_out. */
int autenticar_cliente(int sock, int num_jugador, char* usuario_out, int maxlen) {
	char buf[DIRSIZE];

	/* El cliente puede intentar varias veces hasta autenticarse */
	while (1) {
		if (recibir_msg(sock, buf, sizeof(buf)) <= 0) {
			printf("[Auth J%d] Cliente desconectado\n", num_jugador);
			return 0;
		}

		printf("[Auth J%d] Recibido: %s\n", num_jugador, buf);

		/* Formato esperado: "LOGIN:usuario:contraseña"
						  o  "REGISTRO:usuario:contraseña" */
		char tipo[16], usuario[256], contrasena[256];

		/* Parsear manualmente para evitar problemas con strtok en hijos */
		char copia[DIRSIZE];
		strncpy(copia, buf, sizeof(copia) - 1);
		copia[sizeof(copia) - 1] = '\0';

		char* p1 = strchr(copia, ':');
		if (!p1) {
			enviar_msg(sock, "AUTH_FAIL:formato incorrecto");
			continue;
		}
		*p1 = '\0';
		strncpy(tipo, copia, sizeof(tipo) - 1);
		tipo[sizeof(tipo) - 1] = '\0';

		char* p2 = strchr(p1 + 1, ':');
		if (!p2) {
			enviar_msg(sock, "AUTH_FAIL:formato incorrecto");
			continue;
		}
		*p2 = '\0';
		strncpy(usuario, p1 + 1, sizeof(usuario) - 1);
		usuario[sizeof(usuario) - 1] = '\0';
		strncpy(contrasena, p2 + 1, sizeof(contrasena) - 1);
		contrasena[sizeof(contrasena) - 1] = '\0';

		if (strlen(usuario) == 0 || strlen(contrasena) == 0) {
			enviar_msg(sock, "AUTH_FAIL:usuario o contraseña vacíos");
			continue;
		}

		if (strcmp(tipo, "REGISTRO") == 0) {
			if (registrar_usuario(usuario, contrasena)) {
				printf("[Auth J%d] Registrado: %s\n", num_jugador, usuario);
				enviar_msg(sock, "REGISTRO_OK");
				/* después de registrarse, el cliente enviará LOGIN */
				continue;
			}
			else {
				enviar_msg(sock, "REGISTRO_FAIL:usuario ya existe");
				continue;
			}
		}

		if (strcmp(tipo, "LOGIN") == 0) {
			char pass_almacenada[256];
			if (!buscar_usuario(usuario, pass_almacenada, sizeof(pass_almacenada))) {
				enviar_msg(sock, "AUTH_FAIL:usuario no existe");
				continue;
			}
			if (strcmp(pass_almacenada, contrasena) != 0) {
				enviar_msg(sock, "AUTH_FAIL:contraseña incorrecta");
				continue;
			}
			/* Autenticación exitosa */
			printf("[Auth J%d] Login OK: %s\n", num_jugador, usuario);
			strncpy(usuario_out, usuario, maxlen - 1);
			usuario_out[maxlen - 1] = '\0';
			enviar_msg(sock, "AUTH_OK");
			return 1;
		}

		enviar_msg(sock, "AUTH_FAIL:tipo desconocido");
	}
}

/* ══════════════════════════════════════════════════════════════════════════
   LÓGICA DE UN JUGADOR (corre dentro del fork)

   Pipes:
	 pipe_mi_ataque[1]   → escribo aquí cuando ataco
	 pipe_rival_ataque[0]→ leo aquí cuando el rival atacó

   Protocolo con el cliente:
	 Server → Cliente:  TURNO        (es tu turno, ataca)
	 Cliente → Server:  A5           (coordenada de ataque)
	 Server → Cliente:  TOCADO|A5    (resultado de MI ataque al rival)
						AGUA|A5
	 Server → Cliente:  RIVAL_ATACO|B3|TOCADO   (resultado del ataque rival a mí)
						RIVAL_ATACO|B3|AGUA
	 Server → Cliente:  GANASTE      (fin de partida)
						PERDISTE
   ══════════════════════════════════════════════════════════════════════════ */
void atender_jugador(
	int sd_j, int nj, int turno,
	int pipe_ataque_w,    // escribo mis coords aquí
	int pipe_ataque_r,    // leo coords del rival
	int pipe_res_r,       // leo resultados de mis ataques
	int pipe_res_w        // escribo resultados de ataques rivales
)
{
	char buf[DIRSIZE];
	char mis_barcos[NUM_CELDAS][8];
	int  num_pos = 0;

	const char* reglas =
		"INSTRUCCIONES DEL JUEGO|"
		"1. Cada jugador cuenta con un tablero de 10x10 donde colocará sus barcos.|"
		"2. Coloca estratégicamente tus 5 barcos: Portaaviones(5), Acorazado(4), "
		"Crucero(3), Submarino(3), Destructor(2).|"
		"3. Durante tu turno, elige una coordenada para atacar el tablero enemigo (ej: A5, J10).|"
		"4. Si aciertas a un barco enemigo, se marcará como TOCADO [X].|"
		"5. Si fallas, la casilla se marcará como AGUA [O].|"
		"6. Continúa alternando turnos con tu oponente hasta que uno pierda todos sus barcos.|"
		"7. Para ganar, hunde completamente todos los barcos del enemigo antes que él los tuyos.|"
		"8. Planea tus ataques usando la información de aciertos y fallos.";

	/* 1) Enviar reglas */
	enviar_msg(sd_j, reglas);
	printf("[Hijo%d] Reglas enviadas al Jugador %d\n", nj, nj);

	/* 2) Esperar señal LISTO del cliente (presionó "Iniciar Partida") */
	if (recibir_msg(sd_j, buf, sizeof(buf)) <= 0) {
		printf("[Hijo%d] Cliente desconectado esperando LISTO\n", nj);
		close(sd_j);
		exit(1);
	}
	printf("[Hijo%d] Jugador %d listo: %s\n", nj, nj, buf);

	/* 3) Decirle al cliente que puede colocar sus barcos */
	enviar_msg(sd_j, "COLOCAR_BARCOS");

	/* 4) Recibir las 17 posiciones: "A1,A2,A3,B5,B6,B7,B8,..." */
	if (recibir_msg(sd_j, buf, sizeof(buf)) <= 0) {
		printf("[Hijo%d] Cliente desconectado enviando posiciones\n", nj);
		close(sd_j);
		exit(1);
	}

	num_pos = parsear_posiciones(buf, mis_barcos, NUM_CELDAS);
	printf("[Hijo%d] Jugador %d colocó %d casillas:\n", nj, nj, num_pos);
	/*
	for (int i = 0; i < num_pos; i++) {
		printf("  [%d] %s\n", i, posiciones[i]);
	}
	*/
	enviar_msg(sd_j, "BARCOS_OK");

	/* ── 5) BUCLE DE JUEGO ── */
	while (1) {
		if (turno) {
			enviar_msg(sd_j, "TURNO");
			if (recibir_msg(sd_j, buf, sizeof(buf)) <= 0) goto fin;
			pipe_escribir(pipe_ataque_w, buf);

			char resultado[DIRSIZE];
			if (pipe_leer(pipe_res_r, resultado, sizeof(resultado)) <= 0) goto fin;

			if (strcmp(resultado, "GANASTE") == 0) {
				enviar_msg(sd_j, "GANASTE");
				goto fin;
			}
			char respuesta[DIRSIZE * 2];
			snprintf(respuesta, sizeof(respuesta), "%s|%s", resultado, buf);
			enviar_msg(sd_j, respuesta);
			turno = 0;

		}
		else {
			char coord_rival[16];
			if (pipe_leer(pipe_ataque_r, coord_rival, sizeof(coord_rival)) <= 0) goto fin;

			char resultado[16];
			if (esta_en_posiciones(coord_rival, mis_barcos, num_pos)) {
				marcar_golpeada(coord_rival, mis_barcos, num_pos);
				strcpy(resultado, todos_hundidos(mis_barcos, num_pos)
					? "HUNDIDO_TODO" : "TOCADO");
			}
			else {
				strcpy(resultado, "AGUA");
			}

			int hundido = strcmp(resultado, "HUNDIDO_TODO") == 0;
			pipe_escribir(pipe_res_w, hundido ? "GANASTE" : resultado);

			char notif[DIRSIZE];
			snprintf(notif, sizeof(notif), "RIVAL_ATACO|%s|%s",
				coord_rival, hundido ? "TOCADO" : resultado);
			enviar_msg(sd_j, notif);

			if (hundido) {
				enviar_msg(sd_j, "PERDISTE");
				goto fin;
			}
			turno = 1;
		}
	}

fin:
	printf("[Hijo%d] Fin.\n", nj);
	close(sd_j);
	close(pipe_ataque_w);
	close(pipe_ataque_r);
	close(pipe_res_r);
	close(pipe_res_w);
	exit(0);
}

int main() {

	struct sockaddr_in sind;   /* dirección del servidor */
	struct sockaddr_in pin;    /* dirección del cliente conectado */
	socklen_t addrlen;
	pid_t pid1, pid2;

	/*
	 * Pipes:
	 *   pipe_1a2[0] = Hijo2 lee ataques de Hijo1
	 *   pipe_1a2[1] = Hijo1 escribe sus ataques
	 *   pipe_2a1[0] = Hijo1 lee ataques de Hijo2
	 *   pipe_2a1[1] = Hijo2 escribe sus ataques
	 *
	 *   pipe_res_1[0] = Hijo1 lee resultados de sus ataques (calculados por Hijo2)
	 *   pipe_res_1[1] = Hijo2 escribe resultados del ataque de Hijo1
	 *   pipe_res_2[0] = Hijo2 lee resultados de sus ataques (calculados por Hijo1)
	 *   pipe_res_2[1] = Hijo1 escribe resultados del ataque de Hijo2
	 */

	int pipe_1a2[2];    /* Hijo1 ataca → Hijo2 recibe coord */
	int pipe_2a1[2];    /* Hijo2 ataca → Hijo1 recibe coord */
	int pipe_res_1[2];  /* Hijo2 calcula resultado → Hijo1 lo recibe */
	int pipe_res_2[2];  /* Hijo1 calcula resultado → Hijo2 lo recibe */

	int pipe_j1_listo[2]; 
	int pipe_j2_listo[2];

	int pipe_sync1[2];   /* hijo1 avisa al padre que ya envió AUTH_REQUERIDA */
	int pipe_sync2[2];   /* hijo2 avisa al padre que ya envió AUTH_REQUERIDA */

	if (pipe(pipe_1a2) == -1 ||
		pipe(pipe_2a1) == -1 ||
		pipe(pipe_res_1) == -1 ||
		pipe(pipe_res_2) == -1 ||
		pipe(pipe_j1_listo) == -1 ||
		pipe(pipe_j2_listo) == -1 ||
		pipe(pipe_sync1) == -1 ||
		pipe(pipe_sync2) == -1)
	{
		perror("pipe"); exit(1);
	}

	if (signal(SIGINT, aborta_handler) == SIG_ERR) {
		perror("Could not set signal handler");
		return 1;
	}

	if ((sd = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
		perror("socket");
		exit(1);
	}

	/* Permitir reusar el puerto rápidamente tras cerrar */
	int opt = 1;
	setsockopt(sd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

	memset(&sind, 0, sizeof(sind));
	sind.sin_family = AF_INET;
	sind.sin_addr.s_addr = INADDR_ANY;   /* INADDR_ANY=0x000000 = yo mismo */
	sind.sin_port = htons(PUERTO);       /*  convirtiendo a formato red */

	/* asociando el socket al numero de puerto */
	if (bind(sd, (struct sockaddr*)&sind, sizeof(sind)) == -1) {
		perror("bind");
		exit(1);
	}

	/* ponerse a escuchar a traves del socket */
	if (listen(sd, 5) == -1) {
		perror("listen");
		exit(1);
	}

	addrlen = sizeof(pin);

	/* -------------------------------------------------------
	   CONEXIÓN JUGADOR 1
	------------------------------------------------------- */
	printf("Esperando Jugador 1...\n");

	if ((sd_p1 = accept(sd, (struct sockaddr*)&pin, &addrlen)) == -1) {
		perror("accept jugador1");
		exit(1);
	}
	printf("Jugador 1 conectado. Iniciando autenticación...\n");

	/* -- Fork Hijo 1 -- */
	if ((pid1 = fork()) < 0) { perror("fork hijo1"); exit(1); }

	if (pid1 == 0) {
		/* HIJO 1: atiende Jugador 1 */
		close(sd);
		close(pipe_1a2[0]);     /* no leo mis propios ataques */
		close(pipe_2a1[1]);     /* no escribo en el pipe del rival */
		close(pipe_res_1[1]);   /* no escribo mis propios resultados */
		close(pipe_res_2[0]);   /* no leo resultados del rival */
		close(pipe_j1_listo[0]);    /* no leo mi propio pipe */
		close(pipe_j2_listo[1]);    /* no escribo en el pipe de J2 */
		close(pipe_sync1[0]);   /* hijo no lee su propio pipe de sync */
		close(pipe_sync2[0]);   /* no usa el sync de J2 */
		close(pipe_sync2[1]);

		printf("[Hijo1 pid=%d] Atendiendo Jugador 1\n", getpid());

		/* 1) Enviar AUTH_REQUERIDA ANTES de avisar al padre */
		enviar_msg(sd_p1, "AUTH_REQUERIDA");

		/* 2) Avisar al padre: ya enviamos AUTH_REQUERIDA, puede cerrar su copia */
		write(pipe_sync1[1], "1", 1);
		close(pipe_sync1[1]);

		/* 3) Autenticar */
		if (!autenticar_cliente(sd_p1, 1, usuario_p1, sizeof(usuario_p1))) {
			printf("[Hijo1] J1 falló autenticación.\n");
			close(sd_p1); exit(1);
		}
		printf("[Hijo1] J1 autenticado como: %s\n", usuario_p1);

		/* 4) Bienvenida a J1 */
		char bienvenida[DIRSIZE];
		snprintf(bienvenida, sizeof(bienvenida),
			"Bienvenido %s (Jugador1), esperando conexion de Jugador2", usuario_p1);
		enviar_msg(sd_p1, bienvenida);

		/* 5) Avisar a Hijo2 que J1 ya está listo */
		write(pipe_j1_listo[1], "1", 1);
		close(pipe_j1_listo[1]);
		printf("[Hijo1] Señal enviada a Hijo2: J1 listo\n");

		/* 6) Esperar que J2 también autentique */
		printf("[Hijo1] Esperando que J2 autentique...\n");
		char tmp[2];
		if (read(pipe_j2_listo[0], tmp, 1) <= 0) {
			printf("[Hijo1] Hijo2 cerró el pipe sin señal.\n");
			close(sd_p1); exit(1);
		}
		close(pipe_j2_listo[0]);
		printf("[Hijo1] J2 autenticado. Arrancando juego.\n");

		/* 7) Mandar "Iniciando Juego" a J1 */
		enviar_msg(sd_p1, "Iniciando Juego");

		atender_jugador(sd_p1, 1, 1,          // turno=1, empieza él
			pipe_1a2[1],   // escribe sus ataques
			pipe_2a1[0],   // lee ataques del rival
			pipe_res_1[0], // lee resultados de sus ataques
			pipe_res_2[1]  // escribe resultados de ataques rivales
		);

		exit(0);
	}

	/* PADRE: esperar confirmación de Hijo1 antes de cerrar sd_p1 */
	close(pipe_sync1[1]);
	{ char sb[2]; read(pipe_sync1[0], sb, 1); }
	close(pipe_sync1[0]);
	close(sd_p1);
	printf("[Padre] sd_p1 cerrado de forma segura.\n");

	/* -------------------------------------------------------
	  CONEXIÓN JUGADOR 2
   ------------------------------------------------------- */
	printf("Esperando Jugador 2...\n");

	if ((sd_p2 = accept(sd, (struct sockaddr*)&pin, &addrlen)) == -1) {
		perror("accept jugador2");
		exit(1);
	}

	printf("Jugador 2 conectado. Haciendo fork Hijo2...\n");

	if ((pid2 = fork()) < 0) { perror("fork hijo2"); exit(1); }

	if (pid2 == 0) {
		/* HIJO 2: atiende Jugador 2 */
		close(sd);
		close(pipe_2a1[0]);
		close(pipe_1a2[1]);
		close(pipe_res_2[1]);
		close(pipe_res_1[0]);
		close(pipe_j2_listo[0]);
		close(pipe_j1_listo[1]);
		close(pipe_sync2[0]);
		close(pipe_sync1[1]);
		
		/*
		printf("[Hijo2] sd_p2 = %d\n", sd_p2);
		printf("[Hijo2] pipe_sync1[0]=%d, pipe_sync1[1]=%d\n", pipe_sync1[0], pipe_sync1[1]);
		printf("[Hijo2] pipe_sync2[0]=%d, pipe_sync2[1]=%d\n", pipe_sync2[0], pipe_sync2[1]);
		*/

		/* 1) Auth completa de J2 */
		enviar_msg(sd_p2, "AUTH_REQUERIDA");

		/* 2) Avisar al padre: puede cerrar su copia de sd_p2 */
		write(pipe_sync2[1], "1", 1);
		close(pipe_sync2[1]);

		/* 3) Autenticar */
		if (!autenticar_cliente(sd_p2, 2, usuario_p2, sizeof(usuario_p2))) {
			printf("[Hijo2] J2 falló autenticación.\n");
			close(sd_p2); exit(1);
		}
		printf("[Hijo2] J2 autenticado como: %s\n", usuario_p2);

		/* 4) Bienvenida a J2 */
		char bienvenida[DIRSIZE];
		snprintf(bienvenida, sizeof(bienvenida),
			"Bienvenido %s (Jugador2), el Jugador1 ya esta conectado", usuario_p2);
		enviar_msg(sd_p2, bienvenida);

		/* 5) Avisar a Hijo1 que J2 ya está listo */
		write(pipe_j2_listo[1], "1", 1);
		close(pipe_j2_listo[1]);
		printf("[Hijo2] Señal enviada a Hijo1: J2 listo\n");

		/* 6) Esperar que J1 también haya autenticado */
		printf("[Hijo2] Esperando que J1 autentique...\n");
		char tmp[2];
		if (read(pipe_j1_listo[0], tmp, 1) <= 0) {
			printf("[Hijo2] Hijo1 cerró el pipe sin señal.\n");
			close(sd_p2); exit(1);
		}
		close(pipe_j1_listo[0]);
		printf("[Hijo2] J1 autenticado. Arrancando juego.\n");

		/* 7) Mandar "Iniciando Juego" a J2 */
		enviar_msg(sd_p2, "Iniciando Juego");

		/* 6) Lógica de juego */
		atender_jugador(sd_p2, 2, 0,
			pipe_2a1[1],    /* escribe ataques */
			pipe_1a2[0],    /* lee ataques rival */
			pipe_res_2[0],  /* lee resultados propios */
			pipe_res_1[1]   /* escribe resultados rivales */
		);
		exit(0);
	}

	/* ── PADRE tras fork de Hijo2 ──
	   Misma lógica: espera confirmación antes de cerrar sd_p2. */
	close(pipe_sync2[1]);
	{ char sb[2]; read(pipe_sync2[0], sb, 1); }
	close(pipe_sync2[0]);
	close(sd_p2);
	printf("[Padre] sd_p2 cerrado de forma segura.\n");

	/* El padre cierra el socket de escucha y los pipes de JUEGO.
	   Los pipes pipe_j1_listo y pipe_j2_listo los cierran los hijos;
	   el padre NO los cierra para no generar EOF prematuro. */
	close(sd);
	close(pipe_1a2[0]);   close(pipe_1a2[1]);
	close(pipe_2a1[0]);   close(pipe_2a1[1]);
	close(pipe_res_1[0]); close(pipe_res_1[1]);
	close(pipe_res_2[0]); close(pipe_res_2[1]);

	printf("[Padre] Esperando hijos...\n");
	waitpid(pid1, NULL, 0);
	waitpid(pid2, NULL, 0);
	printf("[Padre] Partida terminada.\n");

	return 0;
}