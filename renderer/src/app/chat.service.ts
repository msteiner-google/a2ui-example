import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { MessageProcessor, Types } from '@a2ui/angular/v0_8';

export interface ChatMessage {
  role: 'user' | 'agent';
  text?: string;
  surfaceId?: string;
}

interface JsonRpcRequest {
  jsonrpc: '2.0';
  id: string;
  method: string;
  params: any;
}

interface JsonRpcResponse {
  jsonrpc: '2.0';
  id: string;
  result?: {
    message: {
      role: string;
      parts: Array<{
        kind: 'text' | 'data';
        text?: string;
        data?: Types.ServerToClientMessage | any;
      }>;
    };
  };
  error?: {
    code: number;
    message: string;
  };
}

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private http = inject(HttpClient);
  private processor = inject(MessageProcessor);
  private readonly API_URL = '/rpc';

  messages = signal<ChatMessage[]>([]);
  isLoading = signal<boolean>(false);
  private rpcIdCounter = 1;

  constructor() {
    // Listen for events from the processor (user interactions)
    this.processor.events.subscribe((event) => {
      console.log('Dispatching A2UI event to server:', event.message);
      this.sendRpcRequest('message/send', {
        message: {
          message_id: `m-event-${Date.now()}`,
          role: 'user',
          parts: [
            {
              kind: 'data',
              data: event.message,
            },
          ],
        },
      });
    });
  }

  addUserMessage(text: string) {
    this.messages.update((m) => [...m, { role: 'user', text }]);
    
    this.sendRpcRequest('message/send', {
      message: {
        message_id: `m-user-${Date.now()}`,
        role: 'user',
        parts: [
          {
            kind: 'text',
            text,
          },
        ],
      },
    });
  }

  addAgentMessage(text: string) {
    this.messages.update((m) => [...m, { role: 'agent', text }]);
  }
private sendRpcRequest(method: string, params: any) {
  const request: JsonRpcRequest = {
    jsonrpc: '2.0',
    id: String(this.rpcIdCounter++),
    method,
    params,
  };

  this.isLoading.set(true);

  // The proxy at /rpc will forward this to http://localhost:8080/ as a POST
  this.http.post<any>(this.API_URL, request).subscribe({
    next: (response) => {
      this.isLoading.set(false);
      console.log('Raw server response:', response);
      if (response.error) {
        console.error('RPC Error:', response.error);
        this.addAgentMessage(`Error: ${response.error.message}`);
      } else {
        // Robustly find the message in the response
        const message = response.result?.status?.message || response.result?.message;
        if (message) {
          this.handleServerMessage(message);
        } else {
          console.warn('No message found in RPC result:', response.result);
        }
      }
    },
    error: (err) => {
      this.isLoading.set(false);
      console.error('HTTP Error (Proxy):', err);
      this.addAgentMessage('Error: Could not connect to the agent server via proxy.');
    },
  });
}


  private handleServerMessage(message: any) {
    console.log('Processing message parts:', message.parts);
    const parts = message.parts || [];
    const a2uiMessages: Types.ServerToClientMessage[] = [];
    const surfaceIdsToTrack = new Set<string>();

    for (const part of parts) {
      if (part.kind === 'text' && part.text) {
        this.addAgentMessage(part.text);
      } else if (part.kind === 'data' && part.data) {
        const msg = part.data as Types.ServerToClientMessage;
        a2uiMessages.push(msg);

        // Identify the surface ID from any message type in the part
        const sId = msg.beginRendering?.surfaceId || 
                    msg.surfaceUpdate?.surfaceId || 
                    msg.dataModelUpdate?.surfaceId;
        
        if (sId) {
          surfaceIdsToTrack.add(sId);
        }
      }
    }

    // Add chat bubbles for new surfaces found in this response
    surfaceIdsToTrack.forEach(surfaceId => {
      // Check if we already have a bubble for this surface in the last few messages
      const alreadyTracked = this.messages().some(m => m.surfaceId === surfaceId);
      if (!alreadyTracked) {
        console.log('Creating chat bubble for surface:', surfaceId);
        this.messages.update((m) => [...m, { role: 'agent', surfaceId }]);
      }
    });

    if (a2uiMessages.length > 0) {
      console.log('Sending messages to A2UI processor:', a2uiMessages);
      this.processor.processMessages(a2uiMessages);

      // Log the state of the surfaces for debugging
      const surfaces = this.processor.getSurfaces();
      surfaces.forEach((surface, id) => {
        console.log(`Surface ${id} tree:`, surface.componentTree);
      });
    }
  }
}
