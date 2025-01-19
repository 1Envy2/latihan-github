import sys
import hashlib
import json

from time import time  # Untuk mendapatkan waktu saat ini
from uuid import uuid4  # Untuk membuat UUID unik untuk node
from flask import Flask  # Framework untuk membuat API
from flask.globals import request  # Untuk mengambil data dari HTTP request
from flask.json import jsonify  # Untuk mengembalikan response dalam format JSON

import requests  # Untuk membuat HTTP request
from urllib.parse import urlparse  # Untuk parsing URL

class Blockchain(object):
    # Target kesulitan proof-of-work, hash harus diawali dengan "0000"
    difficulty_target = "0000"

    # Fungsi untuk membuat hash dari blok
    def hash_block(self, block):
        # Ubah blok menjadi string JSON (dengan kunci terurut) dan encode ke byte
        block_encoded = json.dumps(block, sort_keys=True).encode()
        # Hash hasil encoding menggunakan SHA-256
        return hashlib.sha256(block_encoded).hexdigest()

    def __init__(self):
        self.nodes = set()
        # Inisialisasi rantai blockchain sebagai list kosong
        self.chain = []
        # Inisialisasi daftar transaksi sementara
        self.current_transactions = []

        # Membuat hash untuk blok genesis (blok pertama)
        genesis_hash = self.hash_block("blok pertama")

        # Menambahkan blok genesis ke dalam rantai blockchain
        self.append_block(
            hash_of_previous_block=genesis_hash,
            # Menemukan nonce valid menggunakan fungsi proof_of_work
            nonce=self.proof_of_work(0, genesis_hash, [])
        )

    def add_node(self, address):
        parse_url = urlparse(address)
        self.nodes.add(parse_url.netloc)
        print(parse_url.netloc)

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            
            if block['hash_of_previous_block'] != self.hash_block(last_block):
                return False

            if not self.valid_chain(
                current_index,
                block['hash_of_previous_block'],
                block['transaction'],
                block['nonce']
            ):
                return False

            last_block = block
            current_index +=1

        return True

    def update_blockchain(self):
        neighbours = self.chain
        new_chain = None

        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/blockchain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain
                
                if new_chain:
                    self.chain = new_chain
                    return True

        return False

    # Fungsi untuk menemukan nonce (angka acak) yang memenuhi proof-of-work
    def proof_of_work(self, index, hash_of_previous_block, transactions):
        nonce = 0  # Inisialisasi nonce dengan 0
        # Ulangi sampai hash valid ditemukan
        while self.valid_proof(index, hash_of_previous_block, transactions, nonce) is False:
            nonce += 1  # Tambahkan nonce setiap iterasi
        return nonce

    # Fungsi untuk memvalidasi apakah hash memenuhi syarat kesulitan
    def valid_proof(self, index, hash_of_previous_block, transactions, nonce):
        # Gabungkan data (index, hash sebelumnya, transaksi, nonce) menjadi satu string dan encode ke byte
        content = f'{index}{hash_of_previous_block}{transactions}{nonce}'.encode()
        # Hash data menggunakan SHA-256
        content_hash = hashlib.sha256(content).hexdigest()
        # Periksa apakah hash diawali dengan target kesulitan (contoh: "0000")
        return content_hash[:len(self.difficulty_target)] == self.difficulty_target

    # Fungsi untuk menambahkan blok baru ke dalam blockchain
    def append_block(self, nonce, hash_of_previous_block):
        # Membuat blok baru sebagai dictionary
        block = {
            'index': len(self.chain),  # Indeks blok berdasarkan panjang rantai saat ini
            'timestamp': time(),  # Waktu blok dibuat
            'transaction': self.current_transactions,  # Daftar transaksi dalam blok
            'nonce': nonce,  # Nonce yang ditemukan dengan proof-of-work
            'hash_of_previous_block': hash_of_previous_block  # Hash blok sebelumnya
        }

        # Reset daftar transaksi setelah blok ditambahkan
        self.current_transactions = []

        # Tambahkan blok ke dalam rantai blockchain
        self.chain.append(block)
        return block  # Kembalikan blok yang baru dibuat

    # Fungsi untuk menambahkan transaksi baru ke daftar transaksi sementara
    def add_transaction(self, sender, recipent, amount):
        self.current_transactions.append({
            'amount': amount,  # Jumlah transaksi
            'recipient': recipent,  # Penerima transaksi
            'sender': sender  # Pengirim transaksi
        })
        # Mengembalikan indeks blok berikutnya, tempat transaksi ini akan dimasukkan
        return self.last_block['index'] + 1  

    # Properti untuk mendapatkan blok terakhir dari blockchain
    @property
    def last_block(self):
        return self.chain[-1]  # Mengambil elemen terakhir dalam daftar `self.chain`

# Membuat instance Flask
app = Flask(__name__)

# Membuat identitas unik untuk node ini (digunakan saat mining)
node_identifier = str(uuid4()).replace('-', "")

# Membuat instance blockchain
blockchain = Blockchain()

# Route untuk mendapatkan seluruh rantai blockchain
@app.route('/blockchain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,  # Seluruh blockchain
        'length': len(blockchain.chain)  # Panjang rantai
    }
    return jsonify(response), 200  # Kembalikan response dalam format JSON

# Route untuk mining (menambahkan blok baru)
@app.route('/mine', methods=['GET'])
def mine_block():
    # Tambahkan transaksi baru untuk memberi reward miner
    blockchain.add_transaction(
        sender="0",  # "0" berarti transaksi ini adalah reward untuk miner
        recipent=node_identifier,  # Penerima adalah node ini sendiri
        amount=1  # Jumlah reward
    )

    # Dapatkan hash blok terakhir di blockchain
    last_block_hash = blockchain.hash_block(blockchain.last_block)

    # Temukan nonce yang valid menggunakan proof-of-work
    index = len(blockchain.chain)  # Indeks blok baru
    nonce = blockchain.proof_of_work(index, last_block_hash, blockchain.current_transactions)

    # Tambahkan blok baru ke blockchain
    block = blockchain.append_block(nonce, last_block_hash)
    response = {
        'message': "Block baru telah ditambahkan (mined)",  # Pesan konfirmasi
        'index': block['index'],  # Indeks blok baru
        'hash_of_previous_block': block['hash_of_previous_block'],  # Hash blok sebelumnya
        'transaction': block['transaction']  # Transaksi dalam blok baru
    }
    return jsonify(response), 200

# Route untuk menambahkan transaksi baru
@app.route('/transactions/new', methods=['POST'])    
def new_transactions():
    # Ambil data JSON dari request
    values = request.get_json()

    # Periksa apakah semua field yang diperlukan ada
    required_fields = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required_fields):
        return ('Missing fields', 400)  # Jika ada field yang kurang, kembalikan error

    # Tambahkan transaksi ke daftar transaksi sementara
    index = blockchain.add_transaction(
        values['sender'],  # Pengirim
        values['recipient'],  # Penerima
        values['amount']  # Jumlah
    )

    # Response berhasil
    response = {'message': f'Transaksi akan ditambahkan ke blok {index}'}
    return (jsonify(response), 201)

@app.route('/nodes/add_nodes', methods=['POST'])
def add_nodes():
    values = request.get_json()
    nodes  = values.get('nodes')

    if nodes is None:
        return "Error, missing node(s) info", 400

    for node in nodes:
        blockchain.add_node(node)

    response = {
        'message': 'Node baru telah di tambahkan',
        'nodes': list(blockchain.nodes)
    }

    return jsonify(response), 200 

@app.route('/nodes/sync', methods=['GET'])
def sync():
    updated = blockchain.update_blockchain()
    if updated:
        response = {
            'message': 'BLockchain telah diupdate dengan data terbaru',
            'blockchain': blockchain.chain
        } 
    else:
        response = {
            'message': 'BLockchain sudah menggunakan data terbaru',
            'blockchain': blockchain.chain
        }

    return jsonify(response), 200 

 

# Jalankan aplikasi Flask
if __name__ == '__main__':
    # Gunakan host '0.0.0.0' agar bisa diakses dari luar localhost, port ditentukan dari argumen
    app.run(host='0.0.0.0', port=int(sys.argv[1]))

#testing