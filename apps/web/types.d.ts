declare module 'next' {
  export interface Metadata {
    title?: string;
    description?: string;
  }
}

declare module 'next/link' {
  const Link: any;
  export default Link;
}

declare module 'react' {
  export type ReactNode = any;
}

declare namespace React {
  type ReactNode = any;
}
