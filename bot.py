import os
import requests
from web3 import Web3
import time

# Configura dalle variabili d'ambiente
ETH_RPC_URL = os.getenv('ETH_RPC_URL')
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not all([ETH_RPC_URL, ETHERSCAN_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
    raise Exception("Configura tutte le variabili d'ambiente: ETH_RPC_URL, ETHERSCAN_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID")

w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL))

UNISWAP_FACTORY_ADDRESS = Web3.toChecksumAddress('0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f')

UNISWAP_FACTORY_ABI = [{
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "address", "name": "token0", "type": "address"},
        {"indexed": True, "internalType": "address", "name": "token1", "type": "address"},
        {"indexed": False, "internalType": "address", "name": "pair", "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "", "type": "uint256"}
    ],
    "name": "PairCreated",
    "type": "event"
}]

factory_contract = w3.eth.contract(address=UNISWAP_FACTORY_ADDRESS, abi=UNISWAP_FACTORY_ABI)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def is_verified_on_etherscan(contract_address):
    url = f"https://api.etherscan.io/api?module=contract&action=getsourcecode&address={contract_address}&apikey={ETHERSCAN_API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data['status'] == '1' and len(data['result']) > 0:
            source_code = data['result'][0]['SourceCode']
            return bool(source_code.strip())
    except Exception as e:
        print(f"Errore verifica Etherscan: {e}")
    return False

def get_initial_liquidity(pair_address):
    PAIR_ABI = [{
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"internalType": "uint112", "name": "_reserve0", "type": "uint112"},
            {"internalType": "uint112", "name": "_reserve1", "type": "uint112"},
            {"internalType": "uint32", "name": "_blockTimestampLast", "type": "uint32"}
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }]

    pair = w3.eth.contract(address=pair_address, abi=PAIR_ABI)
    try:
        reserves = pair.functions.getReserves().call()
        return reserves[0], reserves[1]
    except Exception as e:
        print(f"Errore get reserves: {e}")
        return 0, 0

def main():
    print("🟢 Bot Uniswap Pair Created listener avviato...")
    last_block = w3.eth.block_number

    while True:
        try:
            current_block = w3.eth.block_number
            if current_block > last_block:
                events = factory_contract.events.PairCreated().getLogs(fromBlock=last_block+1, toBlock=current_block)
                for event in events:
                    token0 = event.args.token0
                    token1 = event.args.token1
                    pair = event.args.pair

                    verified0 = is_verified_on_etherscan(token0)
                    verified1 = is_verified_on_etherscan(token1)

                    liquidity0, liquidity1 = get_initial_liquidity(pair)

                    msg = (
                        f"🆕 *Nuova Pair Uniswap creata!*\n"
                        f"Token0: [{token0}](https://etherscan.io/address/{token0}) - {'✅ Verificato' if verified0 else '❌ Non verificato'}\n"
                        f"Token1: [{token1}](https://etherscan.io/address/{token1}) - {'✅ Verificato' if verified1 else '❌ Non verificato'}\n"
                        f"Pair: [{pair}](https://etherscan.io/address/{pair})\n"
                        f"Liquidità iniziale:\n"
                        f" - Token0: {liquidity0}\n"
                        f" - Token1: {liquidity1}\n"
                        f"⚠️ *Fare sniper su nuovi token è rischioso!*"
                    )
                    print(msg)
                    send_telegram_message(msg)
                last_block = current_block
            time.sleep(10)
        except Exception as e:
            print(f"Errore nel loop principale: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()
