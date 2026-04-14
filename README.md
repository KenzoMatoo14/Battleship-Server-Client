# BATTLESHIP Server-Client
Este videojuego esta implementado en lenguaje C utilizando una arquitectura Cliente-Servidor.
El servidor gestiona la lógica del juego, la autenticación de usuarios y la comunicación entre dos jugadores conectados mediante sockets.
Cada jugador se conecta como cliente al servidor, el cual crea un proceso independiente (fork) para atender a cada uno. La comunicación entre jugadores se realiza mediante pipes, permitiendo el intercambio de ataques y resultados en tiempo real.

Contiene una interfaz en Python se conecta al servidor mediante sockets, de la misma forma que el cliente en C.
Esta establece conexión con el servidor en el puerto definido. El usuario puede ingresar coordenadas, medienate los pipe, que generan la conexión entre ambos jugadores; el servidor procesa el ataque y responde con el resultado.

# ---- Esquemas del sistema ----

# Procesos Server
  Hijo 1 ───►(Jugador 1)  Hijo 2 ───► (Jugador 2)
  
# Comunicación con pipes
Hijo 1 ───► pipe ───► Hijo 2
Hijo 2 ───► pipe ───► Hijo 1


