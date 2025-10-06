import { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

type QueryResponse = {
  answer: string;
  context: Array<unknown>;
};

export default function ChatPanel() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<Array<{ question: string; answer: string }>>([]);

  const mutation = useMutation<QueryResponse, Error, string>({
    mutationFn: async (prompt) => {
      const response = await axios.post<QueryResponse>("/api/query", {
        question: prompt,
        top_k: 4
      });
      return response.data;
    },
    onSuccess: (data, variables) => {
      setHistory((prev) => [...prev, { question: variables, answer: data.answer }]);
      setQuestion("");
    }
  });

  const isSubmitDisabled = useMemo(() => question.trim().length === 0 || mutation.isPending, [
    question,
    mutation.isPending
  ]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (question.trim().length === 0) return;
    await mutation.mutateAsync(question.trim());
  };

  return (
    <Stack spacing={3} sx={{ maxWidth: 960, margin: "0 auto" }}>
      <Typography variant="h4" component="h1" textAlign="center">
        Fashion Assistant
      </Typography>
      <Paper component="form" onSubmit={handleSubmit} sx={{ padding: 3 }}>
        <Stack spacing={2}>
          <TextField
            label="Ask about care, sizing, or policies"
            multiline
            minRows={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            fullWidth
          />
          <Button
            type="submit"
            variant="contained"
            disabled={isSubmitDisabled}
            endIcon={mutation.isPending ? <CircularProgress size={18} /> : undefined}
          >
            {mutation.isPending ? "Thinking" : "Send"}
          </Button>
        </Stack>
      </Paper>
      {mutation.isError && <Alert severity="error">{mutation.error.message}</Alert>}
      <Stack spacing={2}>
        {history.map((item, index) => (
          <Paper key={index} sx={{ padding: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              You
            </Typography>
            <Typography variant="body1" paragraph>
              {item.question}
            </Typography>
            <Divider sx={{ my: 1 }} />
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Assistant
            </Typography>
            <Typography variant="body1" paragraph sx={{ whiteSpace: "pre-wrap" }}>
              {item.answer}
            </Typography>
          </Paper>
        ))}
        {history.length === 0 && !mutation.isPending && (
          <Box textAlign="center" color="text.secondary">
            <Typography variant="body2">
              Start the conversation by asking about fabric care, fit, or store policies.
            </Typography>
          </Box>
        )}
      </Stack>
    </Stack>
  );
}
