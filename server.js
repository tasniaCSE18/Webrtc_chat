const express = require('express');
const app = express();
const server = require('http').Server(app);
const io = require('socket.io')(server);
const path = require('path');

app.use(express.static(path.join(__dirname, 'public')));

const rooms = new Map();

io.on('connection', (socket) => {
    console.log('User connected:', socket.id);

    socket.on('join-room', (roomId) => {
       
        Array.from(socket.rooms).forEach(room => {
            if (room !== socket.id) socket.leave(room);
        });

        socket.join(roomId);
        
        if (!rooms.has(roomId)) {
            rooms.set(roomId, new Set());
        }
        rooms.get(roomId).add(socket.id);

        socket.to(roomId).emit('user-connected', socket.id);

        const usersInRoom = Array.from(rooms.get(roomId));
        socket.emit('room-users', usersInRoom);
    });

    socket.on('offer', (offer, roomId, targetId) => {
        socket.to(targetId).emit('offer', offer, socket.id);
    });

    socket.on('answer', (answer, roomId, targetId) => {
        socket.to(targetId).emit('answer', answer, socket.id);
    });

    socket.on('ice-candidate', (candidate, roomId, targetId) => {
        socket.to(targetId).emit('ice-candidate', candidate, socket.id);
    });

    socket.on('chat-message', (message, roomId) => {
        io.to(roomId).emit('chat-message', {
            sender: socket.id,
            message: message,
            timestamp: new Date().toISOString()
        });
    });

    socket.on('disconnect', () => {
       
        rooms.forEach((users, roomId) => {
            if (users.has(socket.id)) {
                users.delete(socket.id);
                io.to(roomId).emit('user-disconnected', socket.id);
                if (users.size === 0) {
                    rooms.delete(roomId);
                }
            }
        });
        console.log('User disconnected:', socket.id);
    });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
    console.log(`Open http://localhost:${PORT} in your browser`);
});