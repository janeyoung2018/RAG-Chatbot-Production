import React, { useState } from 'react';

const App = () => {
    const [userInput, setUserInput] = useState('');
    const [responses, setResponses] = useState([]);

    const handleInputChange = (event) => {
        setUserInput(event.target.value);
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: userInput }),
        });
        const data = await response.json();
        setResponses([...responses, { user: userInput, bot: data.reply }]);
        setUserInput('');
    };

    return (
        <div>
            <h1>RAG Chatbot</h1>
            <div>
                {responses.map((res, index) => (
                    <div key={index}>
                        <strong>You:</strong> {res.user}
                        <br />
                        <strong>Bot:</strong> {res.bot}
                    </div>
                ))}
            </div>
            <form onSubmit={handleSubmit}>
                <input
                    type="text"
                    value={userInput}
                    onChange={handleInputChange}
                    placeholder="Type your message..."
                />
                <button type="submit">Send</button>
            </form>
        </div>
    );
};

export default App;