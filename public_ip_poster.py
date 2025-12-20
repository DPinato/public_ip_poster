import argparse
import requests
import os
import logging
import sys
import json
import time
import paramiko

from time import strftime, localtime
from scp import SCPClient


DEFAULT_CONFIG_FILE = "config.json"
DEFAULT_LOG_FILE = "public_ip_poster.log"
DEFAULT_CACHE_DIR = ".public_ip_poster_cache"
DEFAULT_CACHE_FILE = f"{DEFAULT_CACHE_DIR}/public_ip_cache.json"
DEFAULT_CACHE_TTL = 3600  # in seconds

PUBLIC_IP_SERVICE_URL_LIST = [
    "https://ipinfo.io/ip",
    "https://checkip.amazonaws.com"
]


def read_config_file(config_file):
    """Read config file"""
    try:
        with open(config_file, "r") as c:
            config_dict = json.load(c)
        return config_dict
    
    except IOError as e:
        logging.error(f"Failed to read from cache file: {e}")


def validate_ip(ip_address):
    """Basic validation of an IPv4 address."""
    parts = ip_address.split(".")
    if len(parts) != 4 or not all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
        return False
    else:
        return True
    

def get_public_ip():
    """"Retrieve the public IP address from multiple services."""
    public_ip_list = {}

    for service_url in PUBLIC_IP_SERVICE_URL_LIST:
        try:
            logging.info(f"Attempting to retrieve public IP from {service_url}")
            response = requests.get(service_url, timeout=5)
            response.raise_for_status()
            ip_address = response.text.strip()
            if ip_address:
                if validate_ip(ip_address):
                    logging.info(f"Retrieved public IP: {ip_address} from {service_url}")
                    public_ip_list[service_url] = ip_address
        
        except requests.RequestException:
            logging.warning(f"Could not retrieve IP from {service_url}")

    return public_ip_list


def setup_logging(log_file, verbose):
    """Setup logging configuration."""
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level,
                        format=log_format,
                        handlers=[
                            logging.FileHandler(log_file),
                            logging.StreamHandler(sys.stdout)
                        ])


def setup_cache_dir(cache_dir):
    """Ensure the cache directory exists."""
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        logging.info(f"Created cache directory at {cache_dir}")
    else:
        logging.info(f"Using existing cache directory at {cache_dir}")


def save_ip_list_to_cache(cache_file, ip_list):
    """Save the public IP list to a cache file."""
    try:
        timestamp = time.time()
        cache_json = {
            "timestamp":timestamp,
            "services":ip_list
        }
        with open(cache_file, "w") as c:
            json.dump(cache_json, c, indent=4)
        logging.info(f"Saved public IP list to cache file at {cache_file}")
    except IOError as e:
        logging.error(f"Failed to write to cache file: {e}")


def check_cache_staleness(cache_file, ttl):
    """Check if the cache file is stale based on TTL.
        If the file has a timestamp field, use that
        otherwise, check the file's last modification time
    """
    if os.path.exists(cache_file):
        json_cache = {}
        with open(cache_file, "r") as c:
            json_cache = json.load(c)
        
        cache_timestamp = 0.0
        if json_cache["timestamp"]:
            cache_timestamp = json_cache["timestamp"]
            logging.info(f"Cache has timestamp {cache_timestamp}")
        
        else:
            logging.info("Did not find timestamp field in cache")
            cache_timestamp = os.path.getmtime(cache_file)

        current_time = time.time()
        logging.debug(f"current_time: {current_time:.2f} - {strftime('%Y-%m-%d %H:%M:%S', localtime(current_time))}")
        logging.debug(f"cache_timestamp: {cache_timestamp:.2f} - {strftime('%Y-%m-%d %H:%M:%S', localtime(cache_timestamp))}")

        cache_age = current_time - cache_timestamp
        if cache_age < ttl:
            logging.info(f"Cache file is valid, age {cache_age:.2f}")
            try:
                with open(cache_file, "r") as c:
                    cached_ips = json.load(c)
                return cached_ips
            
            except IOError as e:
                logging.error(f"Failed to read from cache file: {e}")
        else:
            logging.info(f"Cache file is stale, older than {ttl} seconds")
    else:
        logging.info(f"No cache file found at {cache_file}")
    
    return None


def run_destination_op(op, cache_file):
    if op["type"] == "scp":
        run_destination_op_scp(op=op,
                               cache_file=cache_file)
    else:
        logging.warning("Don't have option for " + op["type"])
        logging.debug(op)


def run_destination_op_scp(op, cache_file):
    """Basically upload the cache file to the remote server"""
    logging.info(f"Executing operation %s", op["name"])

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=op["host"],
            port=op["port"],
            username=op["username"],
            key_filename=op["identity_file"],
        )
        remote_file = op["remote_dir"] + "/" + os.path.basename(cache_file)
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(
                cache_file,
                remote_path=remote_file,
            )
            logging.info("Uploaded %s to remote %s:%s", cache_file, op["host"], remote_file)

    except Exception as e:
        logging.error("Failed to upload to remote")
        logging.error(e)

    finally:
        ssh.close()
    



def main():
    parser = argparse.ArgumentParser(description="Post public IP address to specified destination")
    parser.add_argument(
        "-c", "--config",
        type=str,
        default=DEFAULT_CONFIG_FILE,
        help=f"Path to configuration file (default: {DEFAULT_CONFIG_FILE})",
    )
    parser.add_argument(
        "-l", "--log-file",
        type=str,
        default=DEFAULT_LOG_FILE,
        help=f"Path to log file (default: {DEFAULT_LOG_FILE})",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
        default=False,
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=DEFAULT_CACHE_DIR,
        help=f"Path to cache directory (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=DEFAULT_CACHE_TTL,
        help=f"Cache time-to-live in seconds (default: {DEFAULT_CACHE_TTL})",
    )
    parser.add_argument(
        "--cache-file",
        type=str,
        default=DEFAULT_CACHE_FILE,
        help=f"Cache filename (default: {DEFAULT_CACHE_FILE})",
    )
    parser.add_argument(
        "--ignore-cache",
        action="store_true",
        help="Ignore cache file, whether stale or not (existing cache will be overwritten)",
        default=False
    )
    
    args = parser.parse_args()

    setup_logging(args.log_file, args.verbose)
    logging.info("public_ip_poster starting")
    logging.debug(args)

    logging.info(f"Using configuration file: {args.config}")
    config_dict = read_config_file(args.config)
    logging.debug(config_dict)
    if not config_dict:
        logging.error(f"Could not read config file from {args.config}")
        os._exit(-1)

    
    setup_cache_dir(args.cache_dir)


    # check if we have public IPs available in cache already, otherwise get fresh ones
    public_ip_list = check_cache_staleness(args.cache_file, args.cache_ttl)
    if public_ip_list and not args.ignore_cache:
        logging.info("Using cached public IP addresses")
        logging.debug(f"Got {len(public_ip_list)}")
        logging.debug(public_ip_list)

    else:
        public_ip_list = get_public_ip()
        logging.info(f"Retrieved {len(public_ip_list)} public IP addresses")
        logging.debug(f"Public IP addresses: {public_ip_list}")

        if not public_ip_list or len(public_ip_list) == 0:
            logging.error("Could not retrieve public IP address from any service, exiting")
            os._exit(-1)

        logging.debug(f"Attempting to save to cache file {args.cache_file}")
        save_ip_list_to_cache(args.cache_file, public_ip_list)




    # run the operations listed in the config file
    dest_list = config_dict["destination_list"]
    logging.info("Got %d destinations", len(config_dict["destination_list"]))
    for dest in dest_list:
        run_destination_op(op=dest,
                           cache_file=args.cache_file)


    logging.info("public_ip_poster finished")

main()