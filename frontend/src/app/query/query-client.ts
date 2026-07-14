import { QueryClient } from "@tanstack/react-query";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";

export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) => {
          if (error instanceof ApiRequestError && error.status >= 400 && error.status < 500) {
            return false;
          }

          return failureCount < 1;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export const appQueryClient = createAppQueryClient();
