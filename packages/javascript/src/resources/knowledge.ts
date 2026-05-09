/**
 * Knowledge resource — knowledge bases, documents, search, library, attachments.
 */

import { del, get, getList, post, put, request, uploadFile } from "../http.js";
import type {
  KnowledgeBase,
  KnowledgeBaseCreate,
  KnowledgeBaseUpdate,
  KnowledgeDocument,
  ResolvedConfig,
  SearchResponse,
  SearchResult,
  WorkforceKnowledgeBaseLink,
} from "../types.js";

export class KnowledgeResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  // ── KB CRUD ───────────────────────────────────────────

  /** List every knowledge base in the caller's library. */
  listAll(): Promise<KnowledgeBase[]> {
    return getList<KnowledgeBase>(this.config, "/knowledge-bases");
  }

  /** List featured / templated knowledge bases. */
  listFeatured(): Promise<KnowledgeBase[]> {
    return getList<KnowledgeBase>(this.config, "/knowledge-bases/featured");
  }

  /**
   * List knowledge bases attached to a workforce.
   *
   * Returns the inner {@link KnowledgeBase} from each attachment record.
   */
  async list(workforceId: string): Promise<KnowledgeBase[]> {
    type AttachItem = { knowledge_base?: KnowledgeBase };
    const payload = await request<AttachItem[] | null>(
      this.config,
      "GET",
      `/workforces/${workforceId}/knowledge-bases`,
    );
    if (!Array.isArray(payload)) {
      return [];
    }
    return payload
      .filter((item): item is { knowledge_base: KnowledgeBase } =>
        Boolean(item && item.knowledge_base),
      )
      .map((item) => item.knowledge_base);
  }

  /** Get a single knowledge base by ID. */
  get(knowledgeBaseId: string): Promise<KnowledgeBase> {
    return get<KnowledgeBase>(
      this.config,
      `/knowledge-bases/${knowledgeBaseId}`,
    );
  }

  /** Create a knowledge base (library or workforce-scoped). */
  create(data: KnowledgeBaseCreate): Promise<KnowledgeBase> {
    return post<KnowledgeBase>(this.config, "/knowledge-bases", data);
  }

  /** Update a knowledge base (server uses PUT). */
  update(
    knowledgeBaseId: string,
    data: KnowledgeBaseUpdate,
  ): Promise<KnowledgeBase> {
    return put<KnowledgeBase>(
      this.config,
      `/knowledge-bases/${knowledgeBaseId}`,
      data,
    );
  }

  /** Delete a knowledge base. */
  delete(knowledgeBaseId: string): Promise<void> {
    return del<void>(this.config, `/knowledge-bases/${knowledgeBaseId}`);
  }

  // ── Workforce attachment ──────────────────────────────

  /** Attach an existing KB to a workforce. */
  attachToWorkforce(
    workforceId: string,
    knowledgeBaseId: string,
  ): Promise<WorkforceKnowledgeBaseLink> {
    return post<WorkforceKnowledgeBaseLink>(
      this.config,
      `/workforces/${workforceId}/knowledge-bases`,
      { knowledge_base_id: knowledgeBaseId },
    );
  }

  /** Detach a KB from a workforce. */
  detachFromWorkforce(
    workforceId: string,
    knowledgeBaseId: string,
  ): Promise<void> {
    return del<void>(
      this.config,
      `/workforces/${workforceId}/knowledge-bases/${knowledgeBaseId}`,
    );
  }

  // ── Documents ─────────────────────────────────────────

  /**
   * Upload a document to a knowledge base.
   *
   * In browsers, pass a `File`. In Node.js 18+, use `File`/`Blob` from
   * `node:buffer`.
   */
  uploadDocument(
    knowledgeBaseId: string,
    file: Blob | File,
    fileName?: string,
  ): Promise<KnowledgeDocument> {
    return uploadFile<KnowledgeDocument>(
      this.config,
      `/knowledge-bases/${knowledgeBaseId}/documents`,
      "file",
      file,
      fileName,
    );
  }

  /** Download the raw bytes for a document. */
  async downloadDocument(
    knowledgeBaseId: string,
    documentId: string,
  ): Promise<ArrayBuffer> {
    const url = new URL(
      `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/download`,
      this.config.baseUrl,
    ).toString();
    const headers: Record<string, string> = {};
    if (this.config.apiKey) {
      headers["X-API-Key"] = this.config.apiKey;
    }
    const response = await fetch(url, {
      method: "GET",
      headers,
      signal: AbortSignal.timeout(this.config.timeout),
    });
    if (!response.ok) {
      throw new Error(
        `Document download failed: ${response.status} ${response.statusText}`,
      );
    }
    return response.arrayBuffer();
  }

  /** Delete a document from a knowledge base. */
  deleteDocument(knowledgeBaseId: string, documentId: string): Promise<void> {
    return del<void>(
      this.config,
      `/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`,
    );
  }

  // ── Search ────────────────────────────────────────────

  /**
   * Run a semantic / keyword search against a KB.
   *
   * Returns the result list directly. Use {@link searchResponse} for the
   * full envelope (including `query` and `total`).
   */
  async search(
    knowledgeBaseId: string,
    query: string,
    options: { topK?: number; filters?: Record<string, unknown> } = {},
  ): Promise<SearchResult[]> {
    const envelope = await this.searchResponse(knowledgeBaseId, query, options);
    return envelope.results;
  }

  /** Run a search and return the full {@link SearchResponse} envelope. */
  searchResponse(
    knowledgeBaseId: string,
    query: string,
    options: { topK?: number; filters?: Record<string, unknown> } = {},
  ): Promise<SearchResponse> {
    const body: Record<string, unknown> = {
      query,
      top_k: options.topK ?? 5,
    };
    if (options.filters !== undefined) {
      body["filters"] = options.filters;
    }
    return post<SearchResponse>(
      this.config,
      `/knowledge-bases/${knowledgeBaseId}/search`,
      body,
    );
  }
}
