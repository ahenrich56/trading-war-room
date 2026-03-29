import base58
from solders.keypair import Keypair
import requests
from config import Config

class WalletManager:
    @staticmethod
    def generate_wallet():
        keypair = Keypair()
        address = str(keypair.pubkey())
        private_key = base58.b58encode(bytes(keypair)).decode('utf-8')
        return address, private_key

    @staticmethod
    def get_balance(address):
        """Returns SOL balance and OPUS token balance."""
        try:
            # SOL Balance
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address]
            }
            response = requests.post(Config.SOLANA_RPC_URL, json=payload)
            sol_balance = response.json()['result']['value'] / 10**9
            
            # OPUS Token Balance
            # OPUS CA: 7qQnePEqSRBxnkFQQJ8jUYXUqo7mSkbwuUHj1jz7pump
            opus_ca = "7qQnePEqSRBxnkFQQJ8jUYXUqo7mSkbwuUHj1jz7pump"
            token_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    address,
                    {"mint": opus_ca},
                    {"encoding": "jsonParsed"}
                ]
            }
            token_response = requests.post(Config.SOLANA_RPC_URL, json=token_payload)
            token_accounts = token_response.json().get('result', {}).get('value', [])
            
            opus_balance = 0
            if token_accounts:
                opus_balance = token_accounts[0]['account']['data']['parsed']['info']['tokenAmount']['uiAmount']
            
            return sol_balance, opus_balance
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return 0, 0

    @staticmethod
    def transfer_funds(from_private_key, to_address, amount_sol=0, amount_tokens=0, token_mint=None):
        """Placeholder for transferring funds (using PumpPortal or Solders)."""
        # In a real implementation, this would use PumpPortal API or Solders to send transactions.
        print(f"Transferring {amount_sol} SOL and {amount_tokens} tokens to {to_address}")
        # Implementation details depend on specific API usage.
        return True, "Transaction Signature Placeholder"
