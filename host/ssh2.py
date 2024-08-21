#ssh2
import csv
import paramiko

# Configuración SSH
host = '10.20.1.101'
usuario = 'admin'
contraseña = 'Vse18163f308'

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

# Conexión SSH al host
cliente_ssh = paramiko.SSHClient()
cliente_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cliente_ssh.connect(hostname=host, username=usuario, password=contraseña)

# Leer el archivo remoto
contenido_remoto = ''
try:
    # Ejecutar el comando para leer el archivo remoto
    _, stdout, _ = cliente_ssh.exec_command(f'cat {ruta_remota}')
    contenido_remoto = stdout.read().decode('utf-8')
except paramiko.SSHException as e:
    print(f'Error al leer el archivo remoto: {e}')

# Extraer los valores de las filas específicas
valores = {}
for fila in contenido_remoto.split('\n'):
    for fila_a_extraer in filas_a_extraer:
        if fila.startswith(fila_a_extraer + '='):
            clave, valor = fila.split('=')
            valores[clave] = valor

# Escribir los datos en un archivo CSV
with open(ruta_csv, 'w', newline='') as archivo_csv:
    escritor_csv = csv.writer(archivo_csv)
    for clave, valor in valores.items():
        escritor_csv.writerow([clave, valor])

print('Los valores se han guardado en el archivo CSV.')

# Cerrar la conexión SSH
cliente_ssh.close()
