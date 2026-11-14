// Numbers of Under the hood that HoodVM (model.ts) does not carry yet. The live adapter fills them;
// the fixture leaves them out, so mock mode shows exactly the wireframe rows.
export interface HoodExtra {
  /** Statements embedded per second (stat embed_rate.per_s). */
  embedRate: number | null
  /** The hardware and model that rate was measured on (stat embed_rate.gpu). */
  embedGpu: string | null
  /** Share of hand-checked pairs where the model's decision matched a person's (stat judge_eval.accuracy). */
  judgeAccuracy: number | null
  /** How many hand-checked pairs (stat judge_eval.n). */
  judgeN: number | null
}
