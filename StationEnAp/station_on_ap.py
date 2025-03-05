import csv
import json
import paramiko
import getpass

def ssh_connect(hostname, username, password):
    """Establece una conexión SSH con el host especificado."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(hostname, username=username, password=password, timeout=10)
        return ssh
    except Exception as e:
        print(f"❌ Error conectando a {hostname}: {e}")
        return None

def execute_command(ssh, command):
    """Ejecuta un comando en el dispositivo remoto y devuelve la salida."""
    stdin, stdout, stderr = ssh.exec_command(command)
    return stdout.read().decode()

def extract_data(json_data):
    """Extrae los datos JSON devueltos por el comando y los convierte en una lista."""
    try:
        devices = json.loads(json_data)
        extracted_data = []
        for device in devices:
            remote = device.get("remote", {})
            hostname = remote.get("hostname", "Unknown")
            platform = device.get("platform", "Unknown")
            lastip = device.get("lastip", "Unknown")
            mac = device.get("mac", "Unknown")
            extracted_data.append([hostname, platform, lastip, mac])
        return extracted_data
    except json.JSONDecodeError:
        print("⚠️ Error al analizar JSON. Verifique la salida del comando.")
        return []

def save_to_csv(data, filename):
    """Guarda los datos extraídos en un archivo CSV."""
    with open(filename, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Hostname", "Platform", "Last IP", "MAC"])
        writer.writerows(data)
    print(f"✅ Datos guardados en {filename}")

def main():
    # Leer las IPs desde el archivo hosts.txt
    try:
        with open("hosts.txt", "r") as file:
            hosts = [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        print("❌ No se encontró el archivo hosts.txt")
        return

    if not hosts:
        print("⚠️ El archivo hosts.txt está vacío")
        return

    # Solicitar usuario y contraseña de manera segura
    username = input("👤 Ingresa tu usuario: ")
    password = getpass.getpass("🔑 Ingresa tu contraseña: ")

    command = "wstalist"

    for hostname in hosts:
        print(f"🔄 Conectando a {hostname}...")
        ssh = ssh_connect(hostname, username, password)
        
        if ssh:
            command_output = execute_command(ssh, command)
            extracted_data = extract_data(command_output)
            
            if extracted_data:
                csv_filename = f"{hostname}.csv"  # Archivo CSV por cada IP
                save_to_csv(extracted_data, csv_filename)
            
            ssh.close()
        else:
            print(f"⚠️ No se pudo conectar a {hostname}")

if __name__ == "__main__":
    main()