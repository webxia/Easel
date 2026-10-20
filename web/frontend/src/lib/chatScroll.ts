/** Follow replies only while the reader stays at the bottom of the chat. */
export class ChatScrollTracker {
  private session = '';
  private userMessages = 0;
  private following = true;

  onScroll(scrollTop: number, scrollHeight: number, clientHeight: number) {
    this.following = scrollHeight - clientHeight - scrollTop <= 64;
  }

  followUpdate(session: string, userMessages: number): boolean {
    if (session !== this.session || userMessages > this.userMessages) this.following = true;
    this.session = session;
    this.userMessages = userMessages;
    return this.following;
  }
}
