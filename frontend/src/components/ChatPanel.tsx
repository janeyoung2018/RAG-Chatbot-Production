import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  Link,
  Paper,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

type ContextItem = {
  type: string;
  id?: string | null;
  title?: string | null;
  text: string;
  score?: number | null;
  source?: string | null;
  metadata?: Record<string, unknown> | null;
};

type QueryResponse = {
  answer: string;
  context: ContextItem[];
  trace_id?: string | null;
  trace_url?: string | null;
};

type ChatTurn = {
  question: string;
  answer: string;
  context: ContextItem[];
  traceId?: string | null;
  traceUrl?: string | null;
};

type MutationPayload = {
  prompt: string;
  filters: { brand?: string; category?: string; tag?: string; size?: string };
  apiKey?: string;
};

export default function ChatPanel() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<Array<ChatTurn>>([]);
  const [apiKey, setApiKey] = useState<string>("");
  const [filters, setFilters] = useState<{ brand: string; category: string; tag: string; size: string }>(
    () => ({ brand: "", category: "", tag: "", size: "" })
  );

  const formatContextSnippet = (text: string) => {
    const trimmed = text.trim();
    if (trimmed.length <= 360) {
      return trimmed;
    }
    return `${trimmed.slice(0, 360)}…`;
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedKey = window.localStorage.getItem("rag_api_key");
    if (storedKey) {
      setApiKey(storedKey);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (apiKey) {
      window.localStorage.setItem("rag_api_key", apiKey);
    } else {
      window.localStorage.removeItem("rag_api_key");
    }
  }, [apiKey]);

  const mutation = useMutation<QueryResponse, Error, MutationPayload>({
    mutationFn: async ({ prompt, filters: requestFilters, apiKey: requestKey }) => {
      const response = await axios.post<QueryResponse>(
        "/api/query",
        {
          question: prompt,
          top_k: 4,
          brand: requestFilters.brand,
          category: requestFilters.category,
          tag: requestFilters.tag,
          size: requestFilters.size
        },
        {
          headers: requestKey ? { "X-API-Key": requestKey } : undefined
        }
      );
      return response.data;
    },
    onSuccess: (data, variables) => {
      setHistory((prev) => [
        ...prev,
        {
          question: variables.prompt,
          answer: data.answer,
          context: data.context ?? [],
          traceId: data.trace_id ?? null,
          traceUrl: data.trace_url ?? null
        }
      ]);
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
    const sanitizedFilters: MutationPayload["filters"] = {
      brand: filters.brand.trim() || undefined,
      category: filters.category.trim() || undefined,
      tag: filters.tag.trim() || undefined,
      size: filters.size.trim() || undefined
    };
    await mutation.mutateAsync({
      prompt: question.trim(),
      filters: sanitizedFilters,
      apiKey: apiKey.trim() || undefined
    });
  };

  return (
    <Stack spacing={3} sx={{ maxWidth: 960, margin: "0 auto" }}>
      <Typography variant="h4" component="h1" textAlign="center">
        Fashion Assistant
      </Typography>
      <Paper component="form" onSubmit={handleSubmit} sx={{ padding: 3 }}>
        <Stack spacing={2}>
          <TextField
            label="API key"
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder="Enter the backend X-API-Key"
            autoComplete="off"
            helperText="Required when the backend enforces authentication"
          />
          <TextField
            label="Ask about care, sizing, or policies"
            multiline
            minRows={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            fullWidth
          />
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              label="Brand filter"
              value={filters.brand}
              onChange={(event) => setFilters((prev) => ({ ...prev, brand: event.target.value }))}
              fullWidth
            />
            <TextField
              label="Category filter"
              value={filters.category}
              onChange={(event) => setFilters((prev) => ({ ...prev, category: event.target.value }))}
              fullWidth
            />
          </Stack>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              label="Tag filter"
              value={filters.tag}
              onChange={(event) => setFilters((prev) => ({ ...prev, tag: event.target.value }))}
              fullWidth
            />
            <TextField
              label="Size filter"
              value={filters.size}
              onChange={(event) => setFilters((prev) => ({ ...prev, size: event.target.value }))}
              fullWidth
            />
          </Stack>
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
            {item.context.length > 0 && (
              <>
                <Divider sx={{ my: 1 }} />
                <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                  Evidence
                </Typography>
                <Stack spacing={1}>
                  {item.context.map((context, contextIndex) => {
                    const infoParts: string[] = [];
                    if (context.source) infoParts.push(String(context.source));
                    if (typeof context.score === "number") {
                      infoParts.push(`score ${context.score.toFixed(3)}`);
                    }
                    if (context.type) infoParts.unshift(context.type);
                    const metadata = context.metadata as Record<string, unknown> | undefined;
                    return (
                      <Paper
                        key={`${item.question}-${contextIndex}`}
                        variant="outlined"
                        sx={{ padding: 1.5, backgroundColor: "grey.50" }}
                      >
                        <Typography variant="subtitle2" fontWeight={600}>
                          {context.title || context.type || `Context ${contextIndex + 1}`}
                        </Typography>
                        {infoParts.length > 0 && (
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ display: "block", mb: 0.5 }}
                          >
                            {infoParts.join(" · ")}
                          </Typography>
                        )}
                        <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                          {formatContextSnippet(context.text)}
                        </Typography>
                        {metadata && Object.keys(metadata).length > 0 && (
                          <Box component="details" sx={{ mt: 1 }}>
                            <Box component="summary" sx={{ cursor: "pointer" }}>
                              Metadata
                            </Box>
                            <Box
                              component="pre"
                              sx={{ whiteSpace: "pre-wrap", fontSize: "0.75rem", mt: 1 }}
                            >
                              {JSON.stringify(metadata, null, 2)}
                            </Box>
                          </Box>
                        )}
                      </Paper>
                    );
                  })}
                </Stack>
              </>
            )}
            {item.traceUrl && (
              <Box mt={1.5}>
                <Link href={item.traceUrl} target="_blank" rel="noreferrer">
                  View Phoenix trace{item.traceId ? ` (${item.traceId.slice(0, 8)})` : ""}
                </Link>
              </Box>
            )}
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
