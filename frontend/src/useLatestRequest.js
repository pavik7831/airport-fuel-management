import { useCallback, useEffect, useRef } from "react";

export function useLatestRequest() {
  const activeController = useRef(null);

  useEffect(
    () => () => {
      activeController.current?.abort();
    },
    [],
  );

  return useCallback((request) => {
    activeController.current?.abort();
    const controller = new globalThis.AbortController();
    activeController.current = controller;

    return Promise.resolve()
      .then(() => request(controller.signal))
      .finally(() => {
        if (activeController.current === controller)
          activeController.current = null;
      });
  }, []);
}
