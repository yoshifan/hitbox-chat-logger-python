import asyncio
import datetime
import json
import logging
import os
import random
import sys

import requests
import websockets



def unwrap_message(wrapped_msg_d):
    # - Under the args key of an object/dict
    # - In a list as the only element
    # - As a string
    return json.loads(wrapped_msg_d['args'][0])



def wrap_message(msg_d):
    return {
        'name': 'message',
        'args': [msg_d],
    }



class ChatClient():
    
    def __init__(self):
        
        # TODO: Have a way to set this to WARNING
        logging.basicConfig(
            format='..........%(levelname)s:%(message)s',
            level=logging.INFO
        )
        
        channel_name_input = input("Which streamer's chat are you joining?: ")
        self.channel_name = channel_name_input.lower()
        
        random.seed()
        random_number = random.randint(100000,999999)
        self.my_username = 'guest_{}'.format(random_number)
        
        chat_server_label = 'hitbox'
        log_filename = '{}__{}.txt'.format(chat_server_label, self.channel_name)
        
        # If the log file exists, show the latest lines from it.
        if os.path.isfile(log_filename):
            print("Found a log file for this chat.")
            print("---------- Last few lines from log ----------")
            with open(log_filename, 'r') as existing_log_file:
                # Make a pass through the file to count lines
                line_count = sum(1 for line in existing_log_file)
                # Reset the file pointer to the beginning
                existing_log_file.seek(0)
                # Read and print the last several lines
                for line_num, line in enumerate(existing_log_file, 1):
                    if line_num > line_count - 10:
                        print(line.strip())
            print("---------- End of log sample ----------")
        else:
            print("You haven't logged anything from this chat yet.")
            
        # Prepare log file for append writes.
        self.log_file = open(log_filename, 'a')

    @asyncio.coroutine
    def connect(self):
        
        chat_servers_url = 'http://api.hitbox.tv/chat/servers?redis=true'
        response = requests.get(chat_servers_url)
        server_ip = response.json()[0]['server_ip']
        
        websocket_id_url = server_ip + '/socket.io/1/'
        response = requests.get('http://' + websocket_id_url)
        # From the response text, get everything before the first colon
        connection_id = response.text[:(response.text.index(':'))]
        
        ws_url = 'ws://' + websocket_id_url + 'websocket/' + connection_id
        self.websocket = yield from websockets.connect(ws_url)
    
    @asyncio.coroutine
    def wait_for_messages(self):
        
        while True:
            received_message = yield from self.websocket.recv()
            logging.info(' << ' + received_message)
            
            if received_message == '1::':
                # Connect confirmation.
                # Reply with a channel join request.
                send_d = {
                    'method': 'joinChannel',
                    'params': {
                        'channel': self.channel_name,
                        'name': self.my_username,
                        'token': '',
                        'isAdmin': False,
                    },
                }
                reply_to_send = '5:::' + json.dumps(wrap_message(send_d))
                
                timestamp_obj = datetime.datetime.now()
                timestamp_str = timestamp_obj.strftime('%Y/%m/%d %H:%M:%S')
                s = "*** [{}] Joining channel: {}".format(
                    timestamp_str, self.channel_name,
                )
                self.log_file.write(s + '\n')
                print(s)
                
            elif received_message == '2::':
                # Ping. Respond with a pong.
                reply_to_send = '2::'
                
            elif received_message.startswith('5:::'):
                receive_d = unwrap_message(json.loads(
                    received_message[len('5:::'):]
                ))
                
                if receive_d['method'] == 'chatMsg':
                    params = receive_d['params']
                    username = params['name']
                    text = params['text']
                    timestamp_obj = datetime.datetime.fromtimestamp(params['time'])
                    timestamp_str = timestamp_obj.strftime('%H:%M:%S')
                    
                    # Log the message.
                    message_str = \
                        '[{}] <{}> {}'.format(timestamp_str, username, text)
                    self.log_file.write(message_str + '\n')
                    print(message_str)
                    reply_to_send = None
                    
                else:
                    # Something else that we don't handle.
                    reply_to_send = None
                
            else:
                # Something else that we don't handle.
                reply_to_send = None
                
            if reply_to_send:
                # Send our reply, if any.
                yield from self.websocket.send(reply_to_send)
                logging.info(' >> ' + reply_to_send)
                
    def part_channel(self):
        # Leave the channel (there's no server disconnect command).
        send_d = {
            'method': 'partChannel',
            'params': {
                'channel': self.channel_name,
                'name': self.my_username,
            },
        }
        reply_to_send = '5:::' + json.dumps(wrap_message(send_d))
        
        logging.info(' >> ' + reply_to_send)
        yield from self.websocket.send(reply_to_send)
        "Leaving the channel."
        
        # Exit the program.
        self.log_file.close()
        sys.exit()





if __name__ == '__main__':
    
    client = ChatClient()
    asyncio.get_event_loop().run_until_complete(client.connect())
    asyncio.get_event_loop().run_until_complete(client.wait_for_messages())
    
