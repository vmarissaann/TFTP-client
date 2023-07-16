import socket, struct, sys, os, shutil

# TFTP packet opcodes
OP_RRQ = 1
OP_WRQ = 2
OP_DATA = 3
OP_ACK = 4
OP_ERROR = 5

#Extension codes
OPT_EXTENSION = 0
OPT_BLKSIZE_CODE = 2
OPT_TSIZE_CODE = 8

# TFTP error codes
ERR_NOT_DEFINED = 0
ERR_FILE_NOT_FOUND = 1
ERR_ACCESS_VIOLATION = 2
ERR_DISK_FULL = 3
ERR_ILLEGAL_OPERATION = 4
ERR_UNKNOWN_TID = 5
ERR_FILE_EXISTS = 6
ERR_NO_SUCH_USER = 7

# TFTP error messages
ERROR_MESSAGES = {
    ERR_NOT_DEFINED: "Not defined",
    ERR_FILE_NOT_FOUND: "File not found",
    ERR_ACCESS_VIOLATION: "Access violation",
    ERR_DISK_FULL: "Disk full or allocation exceeded",
    ERR_ILLEGAL_OPERATION: "Illegal TFTP operation",
    ERR_UNKNOWN_TID: "Unknown transfer ID",
    ERR_FILE_EXISTS: "File already exists",
    ERR_NO_SUCH_USER: "No such user"
}

# TFTP transfer modes
MODE_NETASCII = "netascii"
MODE_OCTET = "octet"

# TFTP default block size and timeout values
DEFAULT_BLOCK_SIZE = 512
DEFAULT_TIMEOUT = 5
DEFAULT_RETRY = 3
DEFAULT_PORT = 69

def create_packet_rrq(filename, mode, block_size=DEFAULT_BLOCK_SIZE, tsize_enabled=True, blksize_enabled=True):
    """
    Create a RRQ (read request) packet.
    Type   Op #     Format without header
            2 bytes    string   1 byte     string   1 byte
            -----------------------------------------------
    RRQ/   | 01 |  Filename  |   0  |    Mode    |   0  |
            -----------------------------------------------
    struct.pack("!H", OP_RRQ): packs the opcode value as an unsigned short (2 bytes) in network byte order.
    filename.encode() converts the filename string into bytes
    mode.encode() converts the mode string into bytes
    b"\x00": null byte

    """
    
    packet = struct.pack("!H", OP_RRQ) + filename.encode() + b"\x00" + mode.encode() + b"\x00"

    if block_size != DEFAULT_BLOCK_SIZE:
        # Append the block size option to the packet data
        packet = append_option(packet, OPT_EXTENSION, OPT_BLKSIZE_CODE)
        packet = append_option(packet, OPT_BLKSIZE_CODE, block_size)

    return packet

def create_packet_wrq(filename, mode):
    """
    Create a WRQ (write request) packet.
    Type   Op #     Format without header
           2 bytes    string   1 byte     string   1 byte
            -----------------------------------------------
    WRQ    | 01 |  Filename  |   0  |    Mode    |   0  |
            -----------------------------------------------
    struct.pack("!H", OP_WRQ): packs the opcode value as an unsigned short (2 bytes) in network byte order.
    filename.encode() converts the filename string into bytes
    mode.encode() converts the mode string into bytes
    b"\x00": null byte

    """
    return struct.pack("!H", OP_WRQ) + filename.encode() + b"\x00" + mode.encode() + b"\x00"

def create_packet_data(block_number, data, block_size=DEFAULT_BLOCK_SIZE):
    """
    Create a DATA packet.

           2 bytes    2 bytes       n bytes
          ---------------------------------
   DATA  | 03    |   Block #  |    Data    |
          ---------------------------------
     data already byte because data = f.read(block_size) is in byte
    """
    if block_size != DEFAULT_BLOCK_SIZE:
        packet = struct.pack("!HH", OP_DATA, block_number) + data
        packet = append_option(packet, OPT_EXTENSION, struct.pack("!H", OPT_BLKSIZE_CODE))
        packet = append_option(packet, OPT_BLKSIZE_CODE, struct.pack("!H", block_size))
    else:
        packet = struct.pack("!HH", OP_DATA, block_number) + data

    return packet

def create_packet_ack(block_number):
    """
    Create an ACK (acknowledgment) packet.
              2 bytes    2 bytes
             -------------------
      ACK   | 04    |   Block #  |
             --------------------
    """
    return struct.pack("!HH", OP_ACK, block_number)

def create_packet_error(error_code, error_message):
    """
    Create an ERROR packet.

            2 bytes  2 bytes        string    1 byte
          ----------------------------------------
   ERROR | 05    |  ErrorCode |   ErrMsg   |   0  |
          ----------------------------------------

    """
    return struct.pack("!HH", OP_ERROR, error_code) + error_message.encode() + b"\x00"

def parse_packet(packet):
    """
    Parse a TFTP packet and return its opcode and payload, including option extension data if present.
    """
    # Unpacks the first 2 bytes of the packet
    opcode = struct.unpack("!H", packet[:2])[0]
    
    if opcode == OP_RRQ or opcode == OP_WRQ:
        # Splits the packet, starting from the third byte (index 2)
        parts = packet[2:].split(b"\x00")
        # Byte strings are decoded into strings
        filename = parts[0].decode()
        mode = parts[1].decode()

        # Check if there are additional options in the packet
        option_start = 2 + len(filename) + 1 + len(mode) + 1  # Start of options (if any)
        if option_start < len(packet):
            options_data = packet[option_start:]
            options = parse_options(options_data)
            return opcode, (filename, mode, options)
        else:
            return opcode, (filename, mode)
    
    elif opcode == OP_DATA:
        block_number = struct.unpack("!H", packet[2:4])[0]
        # Extracts the data content
        # Data starts from index 4 of the packet.
        data = packet[4:]

        return opcode, (block_number, data)
    
    elif opcode == OP_ACK:
        block_number = struct.unpack("!H", packet[2:4])[0]
        return opcode, block_number
    
    elif opcode == OP_ERROR:
        error_code = struct.unpack("!H", packet[2:4])[0]
        # Error message starts from index 4 of the packet
        # Ends at the second-to-last byte of the packet (-1 index).
        error_message = packet[4:-1].decode()
        return opcode, (error_code, error_message)

def append_option(packet_data, option_code, option_value):
    # Append the option code, option length, and option value to the packet data
    if option_code == OPT_BLKSIZE_CODE:
        option_length = 2  # For the blksize option, the length is always 2 bytes
    else:
        raise ValueError("Unsupported option code")

    option_data = struct.pack("!H", option_code) + struct.pack("!H", option_length) + option_value.to_bytes(2, byteorder='big')
    new_packet_data = packet_data + option_data
    return new_packet_data





def parse_options(options_data):
    """
    Parse option extension data from a TFTP packet.
    """
    options = {}
    option_len = len(options_data)
    i = 0

    while i < option_len:
        option_code = struct.unpack("!B", options_data[i:i+1])[0]
        i += 1

        option_length = struct.unpack("!B", options_data[i:i+1])[0]
        i += 1

        option_value = options_data[i:i+option_length]
        i += option_length

        options[option_code] = option_value

    return options




# Function to get user input for the block size
def get_block_size_from_user():
    try:
        block_size = int(input("Enter the desired block size as an integer (default is 512): "))
        if block_size <= 0 or block_size > 65464:
            raise ValueError("Block size must be a positive integer between 1 and 65464.")
        return block_size
    except ValueError as e:
        print("Invalid input:", e)
        return DEFAULT_BLOCK_SIZE

def tftp_client_get(server_ip, server_port, save_dir, client_filename, server_filename=None, mode=MODE_OCTET, block_size=DEFAULT_BLOCK_SIZE, timeout=DEFAULT_TIMEOUT):
    """
    Download a file from a TFTP server.

    :param server_ip: IP address of the TFTP server.

    :param server_port: port number on which the TFTP server is listening

    :param save_dir: directory where the downloaded file will be saved

    :param client_filename: name of the file to be downloaded locally

    :param server_filename:  name of the file found on the TFTP server

    :param mode: represents the TFTP transfer mode
                 default value of MODE_OCTET

    :param block_size: block size for data packets during file transfer
                       default value of DEFAULT_BLOCK_SIZE

    :param timeout: timeout duration
    """
    # if no specific local filename is provided,
    # the downloaded file will be saved using the same name as the original file on the TFTP server
    if server_filename is None:
        server_filename = client_filename

    # Create a UDP socket
    # creates a socket for IPv4 addressing (AF_INET) and using the UDP protocol (SOCK_DGRAM)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    # Creates RRQ packet with options for tsize and blksize
    rrq_packet = create_packet_rrq(client_filename, mode, block_size=block_size)
    # sends RRQ packet
    sock.sendto(rrq_packet, (server_ip, server_port))

    # Receive RRQ response packet with options
    try:
        packet, (server_ip, server_port) = sock.recvfrom(block_size + 4)
    except ConnectionResetError:
        print("Error: Failure to contact server")
        return
    except socket.timeout:
        print("Timeout waiting for server response")
        return

    opcode, payload = parse_packet(packet)

    # Check if the RRQ response contains options
    if opcode == OP_RRQ and len(payload) > 2:
        filename, mode, options_data = payload
        options = parse_options(options_data)

        # Handle the tsize option (RFC 2347)
        if OPT_TSIZE_CODE in options:
            tsize = int(options[OPT_TSIZE_CODE])
            print(f"File size: {tsize} bytes")

        # Handle the blksize option (RFC 2348)
        if OPT_BLKSIZE_CODE in options:
            server_block_size = struct.unpack("!H", options[OPT_BLKSIZE_CODE])[0]
            print(f"Server block size: {server_block_size} bytes")

            # Update block size to match the server's block size
            block_size = server_block_size

    # Save the downloaded file to the specified save_folder
    save_path = os.path.join(save_dir, server_filename)

    # Open the file in binary write mode
    with open(save_path, "wb") as f:
        block_number = 1
        while True:
            try:
                packet, (server_ip, server_port) = sock.recvfrom(block_size + 4)
            except ConnectionResetError:
                print("Error: Failure to contact server")
                f.close()
                # Remove the partially downloaded file
                os.remove(save_path)
                return
            except socket.timeout:
                print("Timeout waiting for server response")
                f.close()
                # Remove the partially downloaded file
                os.remove(save_path)
                return

            opcode, payload = parse_packet(packet)

            if opcode == OP_DATA:
                recv_block_number, data = payload

                if recv_block_number == block_number:
                    f.write(data)
                    # Flush the file buffer to ensure data is written to disk
                    f.flush()
                    free_space = shutil.disk_usage(".").free

                    if free_space < block_size:
                        # creates error packet
                        print(f"Error {ERR_DISK_FULL}: {ERROR_MESSAGES[ERR_DISK_FULL]}")
                        error_packet = create_packet_error(ERR_DISK_FULL, ERROR_MESSAGES[ERR_DISK_FULL])
                        # informs the server that the client's disk space is full
                        sock.sendto(error_packet, (server_ip, server_port))
                        f.close()
                        # removes corrupted file
                        os.remove(save_path)
                        return

                    ack_packet = create_packet_ack(block_number)
                    retries = 0
                    response_received = False
                    while retries < DEFAULT_RETRY and not response_received:
                        try:
                            sock.sendto(ack_packet, (server_ip, server_port))
                            sock.settimeout(timeout)
                            response_received = True
                        except socket.timeout:
                            print("Timeout waiting for server response. Retrying...")
                            retries += 1

                    if not response_received:
                        print("Max retries reached. Failed to receive server response.")
                        f.close()
                        # Remove the partially downloaded file
                        os.remove(save_path)
                        return

                    block_number += 1

                    if len(data) < block_size:
                        print("Download finished!")
                        break
                # if packet gets lost from server
                elif recv_block_number < block_number:
                    ack_packet = create_packet_ack(recv_block_number)
                    sock.sendto(ack_packet, (server_ip, server_port))

            elif opcode == OP_ERROR:
                error_code, error_message = payload
                print(f"Error {error_code}: {error_message}")
                f.close()
                # Remove the partially downloaded file
                os.remove(save_path)
                return

def tftp_client_put(server_ip, file_dir, server_port, client_filename, server_filename=None, mode=MODE_OCTET, block_size=DEFAULT_BLOCK_SIZE, timeout=DEFAULT_TIMEOUT):
    """
    Upload a file to a TFTP server.
    """

    if server_filename is None:
        server_filename = client_filename
    
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    # complete local file path that combines the file directory and filename
    local_filename = os.path.join(file_dir, client_filename)

    # Send WRQ packet
    wrq_packet = create_packet_wrq(server_filename, mode)
    sock.sendto(wrq_packet, (server_ip, server_port))

    # Receive ACK packets and send DATA packets
    if os.path.isfile(local_filename):
        with open(client_filename, "rb") as f:
            block_number = 1
            while True:
                try:
                    packet, (server_ip, server_port) = sock.recvfrom(block_size + 4)
                except socket.timeout:
                    print("Timeout waiting for server response")
                    return

                opcode, payload = parse_packet(packet)

                if opcode == OP_ACK:
                    recv_block_number = payload

                    if recv_block_number + 1 == block_number:
                        data = f.read(block_size)
                        data_packet = create_packet_data(block_number, data)
                        sock.sendto(data_packet, (server_ip, server_port))
                        block_number += 1

                        if len(data) < block_size:
                            print("Upload finished!")
                            break

                elif opcode == OP_ERROR:
                    error_code, error_message = payload
                    print(f"Error {error_code}: {error_message}")
                    return
    else:
        try:
            packet, (server_ip, server_port) = sock.recvfrom(block_size + 4)
        except socket.timeout:
            print("Timeout waiting for server response")
            return
        # creates error packet
        print(f"Error {ERR_FILE_NOT_FOUND}: {ERROR_MESSAGES[ERR_FILE_NOT_FOUND]}")
        error_packet = create_packet_error(ERR_FILE_NOT_FOUND, ERROR_MESSAGES[ERR_FILE_NOT_FOUND])
        # informs the server that the requested file was not found.
        sock.sendto(error_packet, (server_ip, server_port))
        return

def list_files_and_sizes(directory):
    for file in os.listdir(directory):
        if os.path.isfile(os.path.join(directory, file)):
            size = os.path.getsize(os.path.join(directory, file))
            print(f"{file} - {size} bytes")

def get_file_extension(filename):
    return os.path.splitext(filename)[1]

# in the main, ask the user to enter the server IP address, port number, and the file name to be downloaded or uploaded
# then call the appropriate function to download or upload the file
if __name__ == "__main__":
    print('\n' * 50)
    print(" _____  _____  _____  ____     ____  _  _               _")
    print("|_   _||  ___||_   _||  _ \   / ___|| |(_)  ___  _ __  | |_")
    print("  | |  | |_     | |  | |_) | | |    | || | / _ \| '_ \ | __|")
    print("  | |  |  _|    | |  |  __/  | |___ | || ||  __/| | | || |_")
    print("  |_|  |_|      |_|  |_|      \____||_||_| \___||_| |_| \__|")

    server_ip = input("Server IP: ")
    
    while True:

        command = input("Command (get/put/ls/exit): ")
        if command == "exit":
            print("Goodbye!")
            sys.exit(0)

        elif command == "ls":
            print("-----------------------------------")
            list_files_and_sizes(".")
            print("-----------------------------------")

        elif command == "get" or command == "put":
            
            if command == "get":
                server_filename = input("Server Filename: ")
                client_filename = input("Client Filename: ")
                save_folder = input("Which folder do you want to save it in? ")
                block_size = get_block_size_from_user()

                client_extension = get_file_extension(client_filename)
                server_extension = get_file_extension(server_filename)
                if client_extension != server_extension:
                    print("Error: Client and Server file names must have the same extension.")
                    continue
                tftp_client_get(server_ip, DEFAULT_PORT, save_folder, server_filename, client_filename, block_size=block_size)
            
            elif command == "put":
                file_dir = input("File directory of file to upload (Press Enter to use current directory):  ")
                if not file_dir:
                    file_dir = os.getcwd()
                
                os.chdir(file_dir)
                print("-----------------------------------")
                list_files_and_sizes(".")
                print("-----------------------------------")
                client_filename = input("Client Filename: ")
                server_filename = input("Server Filename: ")
                
                client_extension = get_file_extension(client_filename)
                server_extension = get_file_extension(server_filename)
                if client_extension != server_extension:
                    print("Error: Client and Server file names must have the same extension.")
                    continue
                
                tftp_client_put(server_ip, file_dir, DEFAULT_PORT, client_filename, server_filename)
        
        else:
            print("Invalid command")