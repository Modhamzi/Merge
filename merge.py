

import argparse
import base64
import configparser
import json
import threading
import time

import pyaudio
import websocket
from websocket._abnf import ABNF
from playsound import playsound

from ibm_watson.websocket import SynthesizeCallback
from ibm_watson import TextToSpeechV1
from ibm_watson import AssistantV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

 #Setup TTS service 
authenticator = IAMAuthenticator('iIft5SwMJB6zwLwCvkNrKZUpwORZYrS94wqKncjRkFXz') 
tts = TextToSpeechV1(authenticator=authenticator)
tts.set_service_url('https://api.us-south.text-to-speech.watson.cloud.ibm.com/instances/7dbe9d45-03a5-4486-96b3-07d5ee46a103')

#Setup Assistant service
authenticator = IAMAuthenticator('ucOQVynToYJnGvOMp4GvVHFID7GdpIyaY3F97jaznjwE')
assistant = AssistantV2(version='2020-04-01', authenticator = authenticator)
assistant.set_service_url('https://api.us-south.assistant.watson.cloud.ibm.com/instances/eb4b76a8-30e7-4981-9049-050ef7af89cb')

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 5
FINALS = []
LAST = None

REGION_MAP = {
    'us-east': 'gateway-wdc.watsonplatform.net',
    'us-south': 'stream.watsonplatform.net',
    'eu-gb': 'stream.watsonplatform.net',
    'eu-de': 'stream-fra.watsonplatform.net',
    'au-syd': 'gateway-syd.watsonplatform.net',
    'jp-tok': 'gateway-syd.watsonplatform.net',
}


def read_audio(ws, timeout):
    """Read audio and sent it to the websocket port.
    This uses pyaudio to read from a device in chunks and send these
    over the websocket wire.
    """
    global RATE
    p = pyaudio.PyAudio()
  
    RATE = int(p.get_default_input_device_info()['defaultSampleRate'])
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("* recording")
    rec = timeout or RECORD_SECONDS

    for i in range(0, int(RATE / CHUNK * rec)):
        data = stream.read(CHUNK)
  
        ws.send(data, ABNF.OPCODE_BINARY)

    # Disconnect the audio stream
    stream.stop_stream()
    stream.close()
    print("* done recording")
.
    data = {"action": "stop"}
    ws.send(json.dumps(data).encode('utf8'))
    # ... which we need to wait for before we shutdown the websocket
    time.sleep(1)
    ws.close()

    # ... and kill the audio device
    p.terminate()

def on_message(self, msg):

   
    global LAST
    data = json.loads(msg)
    if "results" in data:
        if data["results"][0]["final"]:
            FINALS.append(data)
            LAST = None
        else:
            LAST = data
        output_text = data['results'][0]['alternatives'][0]['transcript']
        print(output_text)
        #STT
        with open ('output.txt','w') as text:
          text.writelines(output_text)
          text.close()
        print (json.dumps(response, indent=2))
        
def on_error(self, error):
    
    print(error)


def on_close(ws):
    global LAST
    if LAST:
        FINALS.append(LAST)
    transcript = "".join([x['results'][0]['alternatives'][0]['transcript']
                          for x in FINALS])
    print(transcript)


def on_open(ws):
    args = ws.args
    data = {
        "action": "start",
        # this means we get to send it straight raw sampling
        "content-type": "audio/l16;rate=%d" % RATE,
        "continuous": True,
        "interim_results": True,
        "word_confidence": True,
        "timestamps": True,
        "max_alternatives": 3
    }

    # binary stream
    ws.send(json.dumps(data).encode('utf8'))

    threading.Thread(target=read_audio,
                     args=(ws, args.timeout)).start()

def get_url():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    
    region = config.get('auth', 'region')
    host = REGION_MAP[region]
    return ("wss://{}/speech-to-text/api/v1/recognize"
           "?model=en-US_BroadbandModel").format(host)

def get_auth():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    apikey = config.get('auth', 'apikey')
    return ("apikey", apikey)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Transcribe Watson text in real time')
    parser.add_argument('-t', '--timeout', type=int, default=5)
    args = parser.parse_args()
    return args


def main():
    # Connect to websocket interfaces
    headers = {}
    userpass = ":".join(get_auth())
    headers["Authorization"] = "Basic " + base64.b64encode(
        userpass.encode()).decode()
    url = get_url()
          
    ws = websocket.WebSocketApp(url,
                                header=headers,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open

    ws.run_forever()
    
    with open('output.txt', 'r') as f:
     tts_Speech = f.readlines()
     tts_Speech = [line.replace('\n', '') for line in tts_Speech]
     tts_Speech = ''.join(str(line) for line in tts_Speech)
     
    #Respons Assistant
    response = assistant.message_stateless(
     assistant_id='2077b151-1b7e-4e43-b72b-4401c495603b', 
     input={ 'message_type': 'text',  'text': tts_Speech }
    ).get_result()
    text   = json.dumps(response, indent=2)
    write  = json.loads(text)
    speech = json.dumps(write["output"]["generic"][0].get("text")) #Get the text response 
    with open('tts_audio.mp3', 'wb') as a:
      res = tts.synthesize(speech, accept='audio/mp3', voice='en-US_AllisonV3Voice').get_result()
      a.write(res.content)
      a.close() 
    print(speech) #print the assistant response
    playsound('tts_audio.mp3') # speech the assistant response
  
if __name__ == "__main__":
    main()