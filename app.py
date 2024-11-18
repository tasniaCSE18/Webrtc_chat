from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = "93220d984aab9c3c12c54c4ba4790e2e"  # Hardcoded secret key for development
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active rooms and their participants
rooms = {}

# HTML template with embedded JavaScript
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Flask WebRTC Chat</title>
    <style>
        body { margin: 0; padding: 20px; font-family: Arial, sans-serif; }
        .container { max-width: 1200px; margin: 0 auto; }
        .video-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .video-wrapper {
            position: relative;
            padding-bottom: 75%;
            background: #f0f0f0;
            border-radius: 8px;
            overflow: hidden;
        }
        .video-wrapper video {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .controls {
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f8f8;
            border-radius: 8px;
        }
        .chat-container {
            position: fixed;
            right: 20px;
            bottom: 20px;
            width: 300px;
            height: 400px;
            border: 1px solid #ccc;
            border-radius: 8px;
            background: white;
            display: flex;
            flex-direction: column;
        }
        #messages {
            flex-grow: 1;
            overflow-y: auto;
            padding: 10px;
        }
        .message {
            margin: 5px 0;
            padding: 5px 10px;
            border-radius: 4px;
            background: #f0f0f0;
        }
        .chat-form {
            padding: 10px;
            border-top: 1px solid #ccc;
            display: flex;
        }
        .chat-form input {
            flex-grow: 1;
            margin-right: 10px;
            padding: 5px;
        }
        button {
            padding: 8px 15px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover { background: #0056b3; }
        input[type="text"] {
            padding: 8px;
            margin-right: 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="controls">
            <input type="text" id="room-input" placeholder="Enter Room ID">
            <button onclick="joinRoom()">Join Room</button>
            <button onclick="toggleAudio()">Toggle Audio</button>
            <button onclick="toggleVideo()">Toggle Video</button>
        </div>
        
        <div class="video-grid" id="video-grid"></div>
        
        <div class="chat-container">
            <div id="messages"></div>
            <form class="chat-form" onsubmit="sendMessage(event)">
                <input type="text" id="message-input" placeholder="Type a message...">
                <button type="submit">Send</button>
            </form>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        let currentRoom = null;
        let localStream = null;
        let peers = {};

        const configuration = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' }
            ]
        };

        async function setupMediaStream() {
            try {
                localStream = await navigator.mediaDevices.getUserMedia({
                    video: true,
                    audio: true
                });
                addVideoStream('local', localStream, true);
                return true;
            } catch (err) {
                console.error('Error accessing media devices:', err);
                return false;
            }
        }

        function addVideoStream(userId, stream, isLocal = false) {
            const videoGrid = document.getElementById('video-grid');
            const videoWrapper = document.createElement('div');
            videoWrapper.className = 'video-wrapper';
            videoWrapper.id = `video-wrapper-${userId}`;
            
            const video = document.createElement('video');
            video.id = `video-${userId}`;
            video.srcObject = stream;
            video.autoplay = true;
            video.playsInline = true;
            if (isLocal) video.muted = true;
            
            videoWrapper.appendChild(video);
            videoGrid.appendChild(videoWrapper);
            
            return video;
        }

        async function joinRoom() {
            const roomId = document.getElementById('room-input').value;
            if (!roomId) return;
            
            if (!localStream) {
                const success = await setupMediaStream();
                if (!success) return;
            }
            
            currentRoom = roomId;
            socket.emit('join', {room: roomId});
        }

        async function createPeerConnection(userId, isInitiator) {
            const peerConnection = new RTCPeerConnection(configuration);
            peers[userId] = peerConnection;

            localStream.getTracks().forEach(track => {
                peerConnection.addTrack(track, localStream);
            });

            peerConnection.ontrack = (event) => {
                if (!document.getElementById(`video-${userId}`)) {
                    addVideoStream(userId, event.streams[0]);
                }
            };

            peerConnection.onicecandidate = (event) => {
                if (event.candidate) {
                    socket.emit('ice_candidate', {
                        candidate: event.candidate,
                        targetId: userId,
                        room: currentRoom
                    });
                }
            };

            if (isInitiator) {
                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                socket.emit('offer', {
                    offer: offer,
                    targetId: userId,
                    room: currentRoom
                });
            }

            return peerConnection;
        }

        function toggleAudio() {
            if (localStream) {
                const audioTrack = localStream.getAudioTracks()[0];
                if (audioTrack) {
                    audioTrack.enabled = !audioTrack.enabled;
                }
            }
        }

        function toggleVideo() {
            if (localStream) {
                const videoTrack = localStream.getVideoTracks()[0];
                if (videoTrack) {
                    videoTrack.enabled = !videoTrack.enabled;
                }
            }
        }

        function sendMessage(event) {
            event.preventDefault();
            const input = document.getElementById('message-input');
            const message = input.value;
            if (message && currentRoom) {
                socket.emit('message', {room: currentRoom, message: message});
                input.value = '';
            }
        }

        // Socket event handlers
        socket.on('user_joined', async (data) => {
            console.log('User joined:', data.userId);
            await createPeerConnection(data.userId, true);
        });

        socket.on('offer', async (data) => {
            console.log('Received offer from:', data.userId);
            const pc = peers[data.userId] || await createPeerConnection(data.userId, false);
            await pc.setRemoteDescription(new RTCSessionDescription(data.offer));
            const answer = await pc.createAnswer();
            await pc.setLocalDescription(answer);
            socket.emit('answer', {
                answer: answer,
                targetId: data.userId,
                room: currentRoom
            });
        });

        socket.on('answer', async (data) => {
            console.log('Received answer from:', data.userId);
            const pc = peers[data.userId];
            if (pc) {
                await pc.setRemoteDescription(new RTCSessionDescription(data.answer));
            }
        });

        socket.on('ice_candidate', async (data) => {
            console.log('Received ICE candidate from:', data.userId);
            const pc = peers[data.userId];
            if (pc) {
                await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
            }
        });

        socket.on('user_left', (data) => {
            console.log('User left:', data.userId);
            if (peers[data.userId]) {
                peers[data.userId].close();
                delete peers[data.userId];
            }
            const videoWrapper = document.getElementById(`video-wrapper-${data.userId}`);
            if (videoWrapper) {
                videoWrapper.remove();
            }
        });

        socket.on('chat_message', (data) => {
            const messages = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message';
            messageDiv.textContent = `${data.userId === socket.id ? 'You' : 'User ' + data.userId.slice(0,4)}: ${data.message}`;
            messages.appendChild(messageDiv);
            messages.scrollTop = messages.scrollHeight;
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    
    if room not in rooms:
        rooms[room] = set()
    
    rooms[room].add(request.sid)
    
    # Notify other users in the room
    emit('user_joined', {'userId': request.sid}, room=room, skip_sid=request.sid)

@socketio.on('offer')
def on_offer(data):
    emit('offer', {
        'offer': data['offer'],
        'userId': request.sid
    }, room=data['targetId'])

@socketio.on('answer')
def on_answer(data):
    emit('answer', {
        'answer': data['answer'],
        'userId': request.sid
    }, room=data['targetId'])

@socketio.on('ice_candidate')
def on_ice_candidate(data):
    emit('ice_candidate', {
        'candidate': data['candidate'],
        'userId': request.sid
    }, room=data['targetId'])

@socketio.on('message')
def on_message(data):
    room = data['room']
    emit('chat_message', {
        'userId': request.sid,
        'message': data['message']
    }, room=room)

@socketio.on('disconnect')
def on_disconnect():
    for room in rooms:
        if request.sid in rooms[room]:
            rooms[room].remove(request.sid)
            emit('user_left', {'userId': request.sid}, room=room)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)