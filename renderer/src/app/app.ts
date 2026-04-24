import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChatService } from './chat.service';
import { Surface } from '@a2ui/angular/v0_8';
import { CommonModule } from '@angular/common';
import { MarkdownPipe } from './markdown.pipe';

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule, Surface, MarkdownPipe],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  chatService = inject(ChatService);
  userInput = '';

  sendMessage() {
    if (this.userInput.trim()) {
      this.chatService.addUserMessage(this.userInput);
      this.userInput = '';
    }
  }
}
