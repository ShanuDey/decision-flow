import { toast } from "sonner";

import { type ApiFailure, errorText, noticeOf } from "./call";

export function errorToast(title: string, error: ApiFailure): void {
  const notice = noticeOf(error);
  toast.error(title, {
    description: (
      <>
        {errorText(error)}
        {notice && (
          <span className="mt-2 block border-t pt-2">
            {notice.text}
            {notice.url && (
              <>
                {" "}
                <a href={notice.url} target="_blank" rel="noreferrer" className="font-semibold underline">
                  Learn more
                </a>
              </>
            )}
          </span>
        )}
      </>
    ),
  });
}
