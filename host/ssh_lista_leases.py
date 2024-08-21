import csv
import paramiko
import getpass

# Ruta del archivo remoto
ruta_remota = '/tmp/system.cfg'
ruta_remota_dhcp = '/var/tmp/dhcpd.leases'

# Ruta del archivo CSV de salida
ruta_csv = 'valores.csv'

# Filas específicas a extraer del archivo system.cfg
filas_a_extraer = [
    'tshaper.1.output.rate',
    'tshaper.1.input.rate',
    'resolv.host.1.name',
    'wireless.1.ssid'
]

# Leer la lista de hosts desde el archivo de texto
hosts = []
with open('hosts.txt', 'r') as archivo_hosts:
    for linea in archivo_hosts:
        hosts.append(linea.strip())

# Solicitar nombre de usuario y contraseña de forma segura
usuario = input("Usuario: ")
contraseña = getpass.getpass("Contraseña: ")

# Conexión y lectura de cada host
for host in hosts:
    # Configuración SSH
    cliente_ssh = paramiko.SSHClient()
    cliente_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Variable para rastrear el estado de la conexión
    conexion_exitosa = True

    try:
        cliente_ssh.connect(hostname=host, username=usuario, password=contraseña)

        # Leer el archivo system.cfg remoto
        _, stdout, _ = cliente_ssh.exec_command(f'cat {ruta_remota}')
        contenido_remoto = stdout.read().decode('utf-8')

        # Extraer los valores del archivo system.cfg
        valores_system = {}
        for fila in contenido_remoto.split('\n'):
            for fila_a_extraer in filas_a_extraer:
                if fila.startswith(fila_a_extraer + '='):
                    clave, valor = fila.split('=')
                    valores_system[clave] = valor

        # Leer el archivo dhcpd.leases remoto
        _, stdout, _ = cliente_ssh.exec_command(f'cat {ruta_remota_dhcp}')
        contenido_dhcpd = stdout.read().decode('utf-8')

        # Extraer los valores del archivo dhcpd.leases
        filas_dhcpd = [
            'timestamp',
            'mac_address',
            'ip',
            'modelo',
            'hostname'
        ]
        valores_dhcpd = {}
        for linea in contenido_dhcpd.split('\n'):
            valores = linea.split()
            if len(valores) == 5:
                for i, fila_dhcpd in enumerate(filas_dhcpd):
                    valores_dhcpd[fila_dhcpd] = valores[i]

        # Escribir los datos en un archivo CSV
        with open(ruta_csv, 'a', newline='') as archivo_csv:
            escritor_csv = csv.writer(archivo_csv)
            fila = [host] + [valores_system.get(fila, '') for fila in filas_a_extraer] + [valores_dhcpd.get(fila, '') for fila in filas_dhcpd]
            escritor_csv.writerow(fila)

        print(f'Los valores del host {host} se han guardado en el archivo CSV.')

    except paramiko.SSHException as e:
        print(f'Error al conectar con el host {host}: {e}')
        conexion_exitosa = False

    finally:
        # Cerrar la conexión SSH
        cliente_ssh.close()

        # Imprimir resultado de la conexión
        if conexion_exitosa:
            print(f'Conexión exitosa con el host {host}')
        else:
            print(f'No se pudo establecer conexión con el host {host}')

    print('---')