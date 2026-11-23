// A message for the person, or null when the error needs none.
export function dictationProblem(code: unknown): string | null {
  switch (code) {
    case "no-speech":
    case "aborted":
      return null;
    case "not-allowed":
      return "Microphone access is blocked. Allow it for this site in the browser settings, then try again.";
    case "audio-capture":
      return "No microphone was found.";
    case "network":
    case "service-not-allowed":
    case "language-not-supported":
      return "Voice input is not available in this browser because its speech service cannot be reached. Try Chrome or Edge, or type your message.";
    default:
      return "Voice input stopped unexpectedly. You can type your message instead.";
  }
}
