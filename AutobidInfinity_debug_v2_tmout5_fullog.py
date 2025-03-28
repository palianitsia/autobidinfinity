import requests
import time
import signal
import sys
import os
import keyboard
import ctypes
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import re
import random

ACCOUNTS_FILE = 'autobidaccounts.txt'
LOG_FILE = 'autobid_bot.log'
ICON_FILE = 'auinfinity.ico'
STOP_BID = False

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

if os.name == "nt" and os.path.exists(ICON_FILE):
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AutobidInfinity")
    
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/88.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 9; SM-J600G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

def create_accounts_file():
    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, 'w') as f:
            f.write("Aggiungi i tuoi account in formato domain:dess a partire dalla seconda riga\n")
        logging.info(f"{ACCOUNTS_FILE} creato. Aggiungi i tuoi account nel formato 'domain:dess'.")

def read_accounts():
    with open(ACCOUNTS_FILE, 'r') as f:
        accounts = f.readlines()[1:]
    return [account.strip().split(':') for account in accounts if account.strip()]

def login(domain, dess):
    session = requests.Session()
    session.cookies.set("dess", dess, domain=f".{domain}", path="/")
    user_agent = random.choice(USER_AGENTS)
    headers = {
        'User -Agent': random.choice(USER_AGENTS)
    }
    url = f"https://{domain}/ajax/get_logged_user.php"
    response = session.get(url, headers=headers, timeout=10)
    if response.status_code == 200 and response.json().get("is_valid"):
        username = response.json().get("username")
        return session, username, user_agent
    return None, None

def get_balance(session, domain):
    url = f"https://{domain}/user_settings.php"
    headers = {
        'User -Agent': random.choice(USER_AGENTS)
    }
    response = session.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        saldo_element = soup.find(id="divSaldoBidBottom")
        return int(saldo_element.text.strip()) if saldo_element else 0
    return 0
    
def get_auction_status(session, domain, auction_id):
    url = f"https://{domain}/data.php?ALL={auction_id}&LISTID=0"
    headers = {
        'User  -Agent': random.choice(USER_AGENTS)
    }
    response = session.get(url, headers=headers, timeout=50)
    
    if response.status_code == 200:
        auction_data = response.text.strip()
        try:
            parts = auction_data.split('*')[1].split(';')
            id_asta = parts[0]
            stato_asta = parts[1]
            prezzo = float(parts[3]) / 100
            vincitore_corrente = parts[4]
            
            return id_asta, stato_asta, prezzo, vincitore_corrente
        except (IndexError, ValueError) as e:
            logging.error(f"Errore nell'analisi dei dati dell'asta: {e}")
            return None, None, None, None
    else:
        logging.error(f"Errore nel recupero dello stato dell'asta: {response.status_code}")
        return None, None, None, None
        
def extract_remaining_bids(response_string):
    # print( response_string )  # Debug
    if not response_string.strip():  
        logging.error("Risposta vuota dal server.")
        return None
    
    match = re.search(r"(ON#|STOP#|OFF#)([^#|]+)", response_string)
    
    if match:
        remaining_bids = match.group(2).strip()
        logging.info(f"Valore estratto correttamente: {remaining_bids}")
        try:
            return int(remaining_bids)
        except ValueError:
            logging.error(f"Formato numero non valido: {remaining_bids}")
            return None
    else:
        logging.error(f"Formato della risposta non valido: {response_string}")
        return None


def get_remaining_auto_bids(session, auction_id, domain):
    url = f"https://{domain}/autobid.php?ID={auction_id}"
    response = session.get(url, timeout=50)
    
    if response.status_code == 200:
        remaining_bids = extract_remaining_bids(response.text)
        if remaining_bids is not None:
            logging.info(f"Puntate rimanenti: {remaining_bids}")
            return remaining_bids
        else:
            logging.error("Errore nell'estrazione del numero di puntate rimanenti.")
    else:
        logging.error(f"Errore nel recupero delle puntate per l'asta: {auction_id}")
    
    return None


def place_auto_bids(session, domain, auction_id, bid_count):
    url = f"https://{domain}/validateInsertAutobid.php"
    data = {'autobidformsubmit': 'true', 'auction_id': auction_id, 'numero_bid': str(bid_count)}
    response = session.post(url, data=data, timeout=50)
    if response.status_code == 200:
        logging.info(f"Puntate inviate: {bid_count} per l'asta: {auction_id}")
        return response.text.split('|')
    logging.error(f"Errore nell'invio delle puntate per l'asta: {auction_id}")
    return None

def run_bot():
    global STOP_BID, session, domain, auction_id 
    print("Benvenuto in AutobidInfinity!  🏴‍☠ ⚖  💯  https://github.com/palianitsia")
    
    accounts = read_accounts()
    
    if not accounts:
        print("Per iniziare aggiungi almeno due account in formato domain:dess - ad/es es.bidoo.com:78fwffe8fw98f7e798ffwfwf4fw424Aes")
        print("Per terminare processo premi Ctrl+C")
    
    auction_id = input("Inserisci ID Asta: ")
    bid_count = int(input("Inserisci numero di puntate da inviare per ciclo: "))
    min_price = float(input("Inserisci prezzo minimo per puntare: "))
    max_price = float(input("Inserisci prezzo massimo da non superare: "))

    current_account_index = 0  
    while current_account_index < len(accounts) and not STOP_BID:
        domain, dess = accounts[current_account_index]
        print(f"Login con account: {domain}")
        logging.info(f"Login con account: {domain}")
        session, username, user_agent = login(domain, dess)

        if session:
            balance = get_balance(session, domain)
            print(f"Login effettuato con 'dess' - {dess}, 'username' - {username}, 'saldo' - {balance}")
            logging.info(f"Login effettuato con 'dess' - {dess}, 'username' - {username}, 'saldo' - {balance}")
            print(f"User  Agent utilizzato per il login: {user_agent}") 
            logging.info(f"User  Agent utilizzato per il login: {user_agent}")
            print(f"Monitorando l'asta {auction_id}...")
            logging.info(f"Monitorando l'asta {auction_id}...")

            bid_sent = False

            while not STOP_BID:
                id_asta, stato_asta, current_price, vincitore_corrente = get_auction_status(session, domain, auction_id)
                remaining_bids = get_remaining_auto_bids(session, auction_id, domain)
                balance = get_balance(session, domain)

                response_string = f"{id_asta}#{stato_asta}"

                logging.info(f"Saldo: {balance}, Puntate rimanenti: {remaining_bids}, Risposta: {response_string}, Prezzo: {current_price:.2f}, Vincitore: {vincitore_corrente}")
                logging.info("Per terminare partecipazione premi Ctrl+C")

                #if stato_asta:
                    #if stato_asta.strip() == 'STOP':
                        #current_time = datetime.now()
                        #if current_time.hour == 10 or current_time.hour == 0:
                            #print("Le aste sono chiuse, ritornaci più tardi.")
                            #break  "se usato va legato a gmt +1" >> rome

                if stato_asta:
                    if stato_asta.strip() == 'STOP':
                        if remaining_bids <= 1:
                            logging.info("Rimanenti 1 o meno puntate, passando al prossimo account...")
                            break
                        else:
                            time.sleep(4) # in base alla connessione
                            
                    elif stato_asta.strip() == 'ON':
                        if remaining_bids <= 1:
                            logging.info("Rimanenti 1 o meno puntate, passando al prossimo account...")
                            break
                        else:
                            time.sleep(4) # in base alla connessione

                    elif stato_asta.strip() == 'OFF':
                        print("Asta terminata oppure non sei abilitato a partecipare in questa asta...")
                        logging.info("Asta terminata oppure non sei abilitato a partecipare in questa asta...")
                        time.sleep(5)
                        print("Riavvio del bot...")
                        logging.info("Riavvio del bot...")
                        run_bot()
                        break

                if current_price and current_price > max_price:
                    logging.info(f"Prezzo massimo raggiunto: {current_price:.2f}, puntate rimanenti rimosse, partecipazione abbandonata.")
                    print("Prezzo massimo raggiunto, terminando la partecipazione...")
                    signal_handler(None, None)
                    return

                if current_price and min_price <= current_price <= max_price and not bid_sent:
                    print("Prezzo nel range, piazzo puntate...")
                    logging.info("Prezzo nel range, piazzo puntate...")
                    print(f"Inviando {bid_count} puntate in auto...")
                    logging.info(f"Inviando {bid_count} puntate in auto...")
                    result = place_auto_bids(session, domain, auction_id, bid_count)
                    if result:
                        #print(f"Saldo: {result[1]}")
                        logging.info(f"Saldo: {bid_count} per l'asta: {auction_id}")
                        bid_sent = True
                    else:
                        logging.error("Errore nell'invio delle puntate.")
                        print("Errore nell'invio delle puntate.")

                time.sleep(1)

        else:
            print("Login fallito, passando al prossimo account.")

        current_account_index += 1  
        if current_account_index >= len(accounts):
            current_account_index = 0

def remove_auto_bids(session, domain, auction_id):
    url = f"https://{domain}/validateRemoveAutobid.php"
    data = {
        'auction_id': auction_id,  # Payload corretto
        'removeautobidsubmit': 'true'
    }
    
    response = session.post(url, data=data, timeout=10)

    print(f"Debug: Risposta del server per la rimozione delle puntate: {response.text}")
    logging.info(f"Debug: Risposta del server per la rimozione delle puntate: {response.text}")

    if response.status_code == 200:
        logging.info(f"Puntate rimosse per l'asta: {auction_id}")
        print(f"Puntate rimosse per l'asta: {auction_id}")
        return True
    else:
        logging.error(f"Errore nella rimozione delle puntate per l'asta: {auction_id}, Codice di stato: {response.status_code}")
        return False

def signal_handler(sig, frame):
    global STOP_BID
    STOP_BID = True
    print("\nTerminazione in corso...")
    logging.info("\nTerminazione in corso...")

    if 'session' in globals() and 'domain' in globals() and 'auction_id' in globals():
        if remove_auto_bids(session, domain, auction_id):
            print("Puntate automatiche rimosse con successo!")
            logging.info("Puntate automatiche rimosse con successo!")
        else:
            print("Errore nella rimozione delle puntate automatiche.")
            logging.info("Errore nella rimozione delle puntate automatiche.")

    time.sleep(5)
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)  
    create_accounts_file()
    run_bot()
