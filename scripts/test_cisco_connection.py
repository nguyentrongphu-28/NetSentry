from getpass import getpass

from app.connectors.ssh_connector import collect_device_info


def main():
    host = input("Cisco management IP: ").strip()
    username = input("SSH username: ").strip()
    password = getpass("SSH password: ")

    try:
        result = collect_device_info(
            host=host,
            username=username,
            password=password,
        )

        print("\nConnection successful!")
        print("Hostname:", result["hostname"])
        print("IP:", result["ip_address"])
        print("\n--- SHOW VERSION ---")
        print(result["version_output"])

        print("\n--- SHOW IP INTERFACE BRIEF ---")
        print(result["interface_output"])

    except Exception as error:
        print("\nConnection failed.")
        print("Error type:", type(error).__name__)
        print("Details:", str(error))


if __name__ == "__main__":
    main()

