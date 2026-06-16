import { defineConfig } from "vitest/config";

// Local config so this nested project does not inherit the parent repo's
// vitest.config.ts (which restricts includes to `tests/`). Our spec keeps the
// suite at `src/order-book.test.ts`.
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    watch: false,
  },
});
