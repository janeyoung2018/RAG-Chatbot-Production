import { Container } from "@mui/material";
import ChatPanel from "./components/ChatPanel";

export default function App() {
  return (
    <Container sx={{ paddingY: 4 }}>
      <ChatPanel />
    </Container>
  );
}
