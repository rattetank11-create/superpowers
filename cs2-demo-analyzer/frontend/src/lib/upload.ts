import { api, ApiError } from "./api";

const MAX_RETRIES = 4;

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Загружает демку чанками с ретраями сетевых ошибок.
 * Ошибки валидации (4xx с кодом) не ретраятся — их показываем пользователю.
 * Возвращает match_id для страницы прогресса.
 */
export async function uploadDemo(
  file: File,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<string> {
  const { upload_id, chunk_size, total_chunks } = await api.createUpload(file.name, file.size);
  for (let i = 0; i < total_chunks; i++) {
    const chunk = file.slice(i * chunk_size, Math.min(file.size, (i + 1) * chunk_size));
    for (let attempt = 0; ; attempt++) {
      if (signal?.aborted) throw new DOMException("aborted", "AbortError");
      try {
        await api.putChunk(upload_id, i, chunk);
        break;
      } catch (err) {
        const retryable = !(err instanceof ApiError) || err.status >= 500;
        if (!retryable || attempt >= MAX_RETRIES) throw err;
        await sleep(1000 * 2 ** attempt);
      }
    }
    onProgress((i + 1) / total_chunks);
  }
  const { match_id } = await api.complete(upload_id);
  return match_id;
}
