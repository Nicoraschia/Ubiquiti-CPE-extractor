# Ubiquiti SSH extractor - Craedo para ISPs

## Descripción

Este script se conecta a una lista de dispositivos mediante SSH y extrae los CPE (clientes) conectados a un AP o de una lista de cliente nos extrae que equipos tienen conectado en la LAN, para saber MAC y modelo del router.

## Datos obtenidos

El script extrae la siguiente información de cada dispositivo:

- `timestamp`: Marca de tiempo de la concesión DHCP.
- `mac_address`: Dirección MAC del dispositivo.
- `ip`: Dirección IP asignada.
- `modelo`: Modelo del dispositivo.
- `hostname`: Nombre de host.


### Archivos 
```
Stations on the AP/
│── hosts.txt
│── station_on_ap.py
│── station_on_ap_ip.py
Cpe_leases/
│── hosts.txt
│── ssh_lista_leases.py
```

## Requisitos

Antes de ejecutar el script, asegúrate de tener instalados los siguientes paquetes de Python:

- `paramiko`

Puedes instalarlos con:

```sh
pip install paramiko
```

## Uso

1. **Preparar la lista de hosts**:

   - Crea un archivo `hosts.txt` en la misma carpeta del script.
   - Agrega una IP por línea, por ejemplo:
     ```
     192.168.1.1
     192.168.1.2
     ```

2. **Ejecutar el script para un solo HOST**:

   - Abre una terminal y navega hasta la carpeta donde se encuentra el script.
   - Ejecuta el script en una linea:
     ```sh
     python station_on_ap_ip.py <IP DEL AP>
     ```
   - Se solicitarán las credenciales SSH (usuario y contraseña) y se creara un fichero CSV

3. **Resultados**:

   - El script guardará los datos en un archivo CSV .
   - Cada fila representará un host con toda la información extraída.

## Manejo de errores

- Si un host no responde, el script continuará con los siguientes.
- En caso de problemas de conexión, se mostrará un mensaje de error en la terminal.

## Créditos 
Nicolas Raschia - 2025.  VERNET INTERNET
Si tienes preguntas o sugerencias, puedes contactarme en nico.otroletravaladna@gmail.com .


---
