declare namespace nodejs {
  interface processenv {
    NODE_ENV: string;
    VUE_ROUTER_MODE: 'hash' | 'history' | 'abstract' | undefined;
    VUE_ROUTER_BASE: string | undefined;
  }
}

interface Window {
  // Set at runtime by Lighthouse CI (injected into index.html) to bypass auth guards.
  __LIGHTHOUSE_BYPASS__?: boolean;
}
