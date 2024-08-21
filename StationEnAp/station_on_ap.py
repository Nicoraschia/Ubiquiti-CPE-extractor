import csv
import json
import paramiko

def ssh_connect(hostname, username, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password)
    return ssh

def execute_command(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    return stdout.read().decode()

def extract_data(json_data):
    devices = json.loads(json_data)
    extracted_data = []
    for device in devices:
        remote = device.get("remote")
        hostname = remote.get("hostname")
        platform = device.get("platform")
        lastip = device.get("lastip")
        mac = device.get("mac")
        extracted_data.append([hostname, platform, lastip, mac])
    return extracted_data

def save_to_csv(data, filename):
    with open(filename, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Hostname", "Platform", "Last IP", "MAC"])
        writer.writerows(data)

def main():
    hostname = "10.20.1.49"  # Reemplaza con la dirección IP del equipo
    username = "admin"  # Reemplaza con tu nombre de usuario
    password = "Vse18163f308"  # Reemplaza con tu contraseña
    command = "wstalist"

    ssh = ssh_connect(hostname, username, password)
    command_output = execute_command(ssh, command)
    extracted_data = extract_data(command_output)
    csv_filename = hostname + ".csv"  # Generar el nombre del archivo CSV usando el hostname
    save_to_csv(extracted_data, csv_filename)

    ssh.close()

if __name__ == "__main__":
    main()