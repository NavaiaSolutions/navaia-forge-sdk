/**
 * Knowledge resource — manage knowledge bases and documents.
 */

import { del, get, getList, post, uploadFile } from "../http.js";
import type {
  KnowledgeBase,
  KnowledgeBaseCreate,
  KnowledgeDocument,
  ResolvedConfig,
} from "../types.js";

export class KnowledgeResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /** List knowledge bases for a workforce. */
  list(workforceId: string): Promise<KnowledgeBase[]> {
    return getList<KnowledgeBase>(
      this.config,
      "/knowledge-bases",
      { workforce_id: workforceId },
    );
  }

  /** Get a single knowledge base by ID. */
  get(knowledgeBaseId: string): Promise<KnowledgeBase> {
    return get<KnowledgeBase>(
      this.config,
      `/knowledge-bases/${knowledgeBaseId}`,
    );
  }

  /** Create a new knowledge base. */
  create(data: KnowledgeBaseCreate): Promise<KnowledgeBase> {
    return post<KnowledgeBase>(this.config, "/knowledge-bases", data);
  }

  /** Delete a knowledge base. */
  delete(knowledgeBaseId: string): Promise<void> {
    return del<void>(this.config, `/knowledge-bases/${knowledgeBaseId}`);
  }

  /**
   * Upload a document to a knowledge base.
   *
   * In browsers, pass a `File` object. In Node.js 18+, use the built-in
   * `File` or `Blob` from `node:buffer`.
   *
   * @param knowledgeBaseId - The knowledge base to upload to.
   * @param file - The file to upload.
   * @param fileName - Optional file name override.
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

  /**
   * Delete a document from a knowledge base.
   *
   * @param knowledgeBaseId - The knowledge base the document belongs to.
   * @param documentId - The document to delete.
   */
  deleteDocument(knowledgeBaseId: string, documentId: string): Promise<void> {
    return del<void>(
      this.config,
      `/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`,
    );
  }
}
