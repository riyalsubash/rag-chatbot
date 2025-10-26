            function addMessage(text, isUser) {
                const messagesDiv = document.getElementById('messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
                messageDiv.textContent = text;
                messagesDiv.appendChild(messageDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }

            async function uploadFiles() {
                const fileInput = document.getElementById('fileInput');
                const files = fileInput.files;
                const statusDiv = document.getElementById('uploadStatus');
                const uploadBtn = document.getElementById('uploadBtn');
                
                if (files.length === 0) {
                    statusDiv.innerHTML = '<div class="status error">Please select files</div>';
                    return;
                }

                const formData = new FormData();
                for (let file of files) {
                    formData.append('files', file);
                }

                statusDiv.innerHTML = '<div class="status info"><span class="loading"></span> Processing documents... This may take a minute.</div>';
                uploadBtn.disabled = true;
                
                try {
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        statusDiv.innerHTML = `<div class="status success">✓ ${data.message}</div>`;
                        displayFileList(data.files);
                    } else {
                        statusDiv.innerHTML = `<div class="status error">✗ ${data.error}</div>`;
                    }
                } catch (error) {
                    statusDiv.innerHTML = `<div class="status error">✗ Upload failed: ${error}</div>`;
                } finally {
                    uploadBtn.disabled = false;
                }
            }

            function displayFileList(files) {
                const fileListDiv = document.getElementById('fileList');
                fileListDiv.innerHTML = '<strong>Uploaded:</strong>' + 
                    files.map(f => `<div class="file-item">📄 ${f}</div>`).join('');
            }

            async function askQuestion() {
                const input = document.getElementById('questionInput');
                const question = input.value.trim();
                const askBtn = document.getElementById('askBtn');
                
                if (!question) return;
                
                addMessage(question, true);
                input.value = '';
                askBtn.disabled = true;
                
                // Add loading message
                const messagesDiv = document.getElementById('messages');
                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'message bot-message';
                loadingDiv.innerHTML = '<span class="loading"></span> Claude is thinking...';
                loadingDiv.id = 'loading-message';
                messagesDiv.appendChild(loadingDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                
                try {
                    const response = await fetch('/ask', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({question})
                    });
                    const data = await response.json();
                    
                    // Remove loading message
                    const loading = document.getElementById('loading-message');
                    if (loading) loading.remove();
                    
                    if (data.success) {
                        addMessage(data.answer, false);
                    } else {
                        addMessage('❌ Error: ' + data.error, false);
                    }
                } catch (error) {
                    const loading = document.getElementById('loading-message');
                    if (loading) loading.remove();
                    addMessage('❌ Error: ' + error, false);
                } finally {
                    askBtn.disabled = false;
                }
            }