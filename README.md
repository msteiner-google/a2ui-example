```
   curl -X POST http://localhost:8080/ \
        -H "Content-Type: application/json" \
        -d '{
          "jsonrpc": "2.0",
          "id": "1",
          "method": "message/send",
          "params": {
            "message": {
              "message_id": "m1",
              "role": "user",
              "parts": [
                {
                  "kind": "text",
                  "text": "Hello"
                }
              ]
            }
          }
        }'
```
