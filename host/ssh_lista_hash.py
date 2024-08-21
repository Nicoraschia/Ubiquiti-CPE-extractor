import csv
import getpass
import hashlib
import paramiko

# Ruta del archivo remoto
ruta_remota = '/tmp/system.cfg'

# Ruta del archivo CSV de salida
ruta_csv = 'valores.csv'

# Filas específicas a extraer
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

# Solicitar las credenciales de usuario y contraseña
usuario = input("Usuario: ")
contraseña = getpass.getpass("Contraseña: ")

# Encriptar la contraseña
hashed_contraseña = hashlib.sha256(contraseña.encode()).hexdigest()

# Escribir los encabezados del archivo CSV
with open(ruta_csv, 'w', newline='') as archivo_csv:
    escritor_csv = csv.writer(archivo_csv)
    encabezados = ['Host'] + filas_a_extraer
    escritor_csv.writerow(encabezados)

# Conexión y lectura de cada host
for host in hosts:
    # Conexión SSH al host
    cliente_ssh = paramiko.SSHClient()
    cliente_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Variable para rastrear el estado de la conexión
    conexion_exitosa = True

    try:
        cliente_ssh.connect(hostname=host, username=usuario, password=contraseña)

        # Leer el archivo remoto
        contenido_remoto = ''
        _, stdout, _ = cliente_ssh.exec_command(f'cat {ruta_remota}')
        contenido_remoto = stdout.read().decode('utf-8')

        # Extraer los valores de las filas específicas
        valores = {}
        for fila in contenido_remoto.split('\n'):
            for fila_a_extraer in filas_a_extraer:
                if fila.startswith(fila_a_extraer + '='):
                    clave, valor = fila.split('=')
                    valores[clave] = valor

        # Escribir una sola fila en el archivo CSV para el host actual
        with open(ruta_csv, 'a', newline='') as archivo_csv:
            escritor_csv = csv.writer(archivo_csv)
            fila_csv = [host] + [valores.get(fila, '') for fila in filas_a_extraer]
            escritor_csv.writerow(fila_csv)

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
