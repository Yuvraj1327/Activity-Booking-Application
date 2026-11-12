import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

const eslintConfig = [
  ...coreWebVitals,
  ...typescript,
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts", "e2e/report/**", "e2e/.stack/**", "test-results/**", "playwright-report/**"] },
];

export default eslintConfig;
