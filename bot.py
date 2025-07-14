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
    raise Exception(
        "Configura tutte le variabili d'ambiente: "
        "ETH_RPC_URL, ETHERSCAN_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID"
    )

w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL))

UNISWAP_FACTORY_ADDRESS = w3.to_checksum_address(
    '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f'
)

UNISWAP_FACTORY_ABI = [{
    "anonymous": False,
    "inputs": [
        {"indexed": True,  "internalType": "address", "name": "token0", "type": "address"},
        {"indexed": True,  "internalType": "address", "name": "token1", "type": "address"},
        {"indexed": False, "internalType": "address", "name": "pair",   "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "",       "type": "uint256"}
    ],
    "name": "PairCreated",
    "type": "event"
}]

factory_contract = w3.eth.contract(
    address=UNISWAP_FACTORY_ADDRESS,
    abi=UNISWAP_FACTORY_ABI
)

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
    url = (
        f"https://api.etherscan.io/api?"
        f"module=contract&action=getsourcecode&address={contract_address}"
        f"&apikey={ETHERSCAN_API_KEY}"
    )
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == '1' and data.get('result'):
            return bool(data['result'][0]['SourceCode'].strip())
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
            {"internalType": "uint32",  "name": "_blockTimestampLast", "type": "uint32"}
        ],
        "stateMutability": "view",
        "type": "function"
    }]
    pair = w3.eth.contract(address=pair_address, abi=PAIR_ABI)
    try:
        r0, r1, _ = pair.functions.getReserves().call()
        return r0, r1
    except Exception as e:
        print(f"Errore get reserves: {e}")
        return 0, 0

def main():
    print("🟢 Bot Uniswap PairCreated listener avviato...")

    # filtro eventi da adesso in poi
    pair_filter = factory_contract.events.PairCreated.createFilter(fromBlock='latest')

    while True:
        try:
            events = pair_filter.get_new_entries()
            for ev in events:
                token0 = ev['args']['token0']
                token1 = ev['args']['token1']
                pair   = ev['args']['pair']

                verified0 = is_verified_on_etherscan(token0)
                verified1 = is_verified_on_etherscan(token1)

                liq0, liq1 = get_initial_liquidity(pair)

                msg = (
                    f"🆕 *Nuova Pair Uniswap creata!*\n"
                    f"• Token0: [{token0}](https://etherscan.io/address/{token0}) "
                    f"- {'✅ Verificato' if verified0 else '❌ Non verificato'}\n"
                    f"• Token1: [{token1}](https://etherscan.io/address/{token1}) "
                    f"- {'✅ Verificato' if verified1 else '❌ Non verificato'}\n"
                    f"• Pair: [{pair}](https://etherscan.io/address/{pair})\n"
                    f"• Liquidità iniziale: {liq0} / {liq1}\n"
                    f"⚠️ *Fare sniper su nuovi token è rischioso!*"
                )
                print(msg)
                send_telegram_message(msg)

            time.sleep(10)

        except Exception as e:
            print(f"Errore nel loop principale: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
