#
#
# Comando para Ejecutar: python station_on_ap_ip.py <dirección IP de AP>
# By Nicolas Raschia - 2025
#
#

import csv
import json
import paramiko
import sys
import getpass


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
        remote = device.get("remote", {})
        hostname = remote.get("hostname", "Unknown")
        platform = remote.get("platform", "Unknown")
        lastip = device.get("lastip", "Unknown")
        mac = device.get("mac", "Unknown")
        extracted_data.append([hostname, platform, lastip, mac])
    return extracted_data


def save_to_csv(data, filename):
    with open(filename, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Hostname", "Platform", "Last IP", "MAC"])
        writer.writerows(data)


def main():
    if len(sys.argv) != 2:
        print("Debe proporcionar la dirección IP del AP como argumento.")
        print("Uso: python station_on_ap_ip.py <dirección IP>")
        return

    ip_address = sys.argv[1]
    username = input("Ingrese el nombre de usuario: ")
    password = getpass.getpass("Ingrese la contraseña: ")
    command = "wstalist"

    try:
        ssh = ssh_connect(ip_address, username, password)
        command_output = execute_command(ssh, command)
        extracted_data = extract_data(command_output)
        csv_filename = f"{ip_address}.csv"  # Generar el nombre del archivo CSV usando la dirección IP
        save_to_csv(extracted_data, csv_filename)
        print(f"Datos guardados en {csv_filename}")
        ssh.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

