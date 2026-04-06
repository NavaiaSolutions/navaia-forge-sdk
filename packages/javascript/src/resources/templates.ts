/**
 * Template resource — browse and instantiate workforce templates.
 */

import { get, getList, post } from "../http.js";
import type {
  ResolvedConfig,
  Template,
  Workforce,
} from "../types.js";

export class TemplateResource {
  private readonly config: ResolvedConfig;

  constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /** List all available workforce templates. */
  list(): Promise<Template[]> {
    return getList<Template>(this.config, "/workforce-templates");
  }

  /** Get a single template by ID. */
  get(templateId: string): Promise<Template> {
    return get<Template>(this.config, `/workforce-templates/${templateId}`);
  }

  /**
   * Instantiate a template to create a new workforce.
   *
   * @param templateId - The template to instantiate.
   * @param name - Name for the new workforce.
   */
  instantiate(templateId: string, name: string): Promise<Workforce> {
    return post<Workforce>(
      this.config,
      `/workforce-templates/${templateId}/instantiate`,
      { name },
    );
  }
}
