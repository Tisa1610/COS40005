# MQTT quick setup

1) Drop TLS files into `../tls/`.
2) Create a user:
   docker run --rm -v "%cd%:/mosquitto" eclipse-mosquitto:2 mosquitto_passwd -c /mosquitto/config/passwd rtm_agent
3) Run broker (Docker Desktop):
   docker run -it --name mqtt -p 8883:8883 ^
     -v "%cd%:/mosquitto" eclipse-mosquitto:2
