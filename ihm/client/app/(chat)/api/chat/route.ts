// MODIFIED: Simplified version that proxies to FastAPI backend at localhost:8000
// Original imports commented out for reference
// import { geolocation } from "@vercel/functions";
// import {
//   convertToModelMessages,
//   createUIMessageStream,
//   JsonToSseTransformStream,
//   smoothStream,
//   stepCountIs,
//   streamText,
// } from "ai";
// import { unstable_cache as cache } from "next/cache";
// import { after } from "next/server";
// import {
//   createResumableStreamContext,
//   type ResumableStreamContext,
// } from "resumable-stream";
// import type { ModelCatalog } from "tokenlens/core";
// import { fetchModels } from "tokenlens/fetch";
// import { getUsage } from "tokenlens/helpers";
import { auth, type UserType } from "@/app/(auth)/auth";
import type { VisibilityType } from "@/components/visibility-selector";
import { entitlementsByUserType } from "@/lib/ai/entitlements";
import type { ChatModel } from "@/lib/ai/models";
// import { type RequestHints, systemPrompt } from "@/lib/ai/prompts";
// import { myProvider } from "@/lib/ai/providers";
// import { createDocument } from "@/lib/ai/tools/create-document";
// import { getWeather } from "@/lib/ai/tools/get-weather";
// import { requestSuggestions } from "@/lib/ai/tools/request-suggestions";
// import { updateDocument } from "@/lib/ai/tools/update-document";
// import { isProductionEnvironment } from "@/lib/constants";
import {
  // createStreamId,
  deleteChatById,
  getChatById,
  getMessageCountByUserId,
  // getMessagesByChatId,
  saveChat,
  saveMessages,
  // updateChatLastContextById,
} from "@/lib/db/queries";
import { ChatSDKError } from "@/lib/errors";
import type { ChatMessage } from "@/lib/types";
// import type { AppUsage } from "@/lib/usage";
// import { convertToUIMessages } from "@/lib/utils";
import { generateUUID } from "@/lib/utils";
import { generateTitleFromUserMessage } from "../../actions";
import { type PostRequestBody, postRequestBodySchema } from "./schema";

export const maxDuration = 600; // 10 minutes timeout

// let globalStreamContext: ResumableStreamContext | null = null;

// const getTokenlensCatalog = cache(
//   async (): Promise<ModelCatalog | undefined> => {
//     try {
//       return await fetchModels();
//     } catch (err) {
//       console.warn(
//         "TokenLens: catalog fetch failed, using default catalog",
//         err
//       );
//       return; // tokenlens helpers will fall back to defaultCatalog
//     }
//   },
//   ["tokenlens-catalog"],
//   { revalidate: 24 * 60 * 60 } // 24 hours
// );

// export function getStreamContext() {
//   if (!globalStreamContext) {
//     try {
//       globalStreamContext = createResumableStreamContext({
//         waitUntil: after,
//       });
//     } catch (error: any) {
//       if (error.message.includes("REDIS_URL")) {
//         console.log(
//           " > Resumable streams are disabled due to missing REDIS_URL"
//         );
//       } else {
//         console.error(error);
//       }
//     }
//   }
//
//   return globalStreamContext;
// }

export async function POST(request: Request) {
  let requestBody: PostRequestBody;

  try {
    const json = await request.json();
    requestBody = postRequestBodySchema.parse(json);
  } catch (_) {
    return new ChatSDKError("bad_request:api").toResponse();
  }

  try {
    const {
      id,
      message,
      selectedChatModel,
      selectedVisibilityType,
      sessionId,
    }: {
      id: string;
      message: ChatMessage;
      selectedChatModel: ChatModel["id"];
      selectedVisibilityType: VisibilityType;
      sessionId?: string;
    } = requestBody;

    const session = await auth();

    if (!session?.user) {
      return new ChatSDKError("unauthorized").toResponse();
    }

    const userId = session.user.id;
    const userType: UserType = session.user.type;

    console.log(`[API Route] Session found: User ID ${userId}, Type: ${userType}`);

    const messageCount = await getMessageCountByUserId({
      id: userId,
      differenceInHours: 24,
    });

    if (messageCount > entitlementsByUserType[userType].maxMessagesPerDay) {
      return new ChatSDKError("rate_limit:chat").toResponse();
    }

    const chat = await getChatById({ id });

    if (chat) {
      if (chat.userId !== userId) {
        return new ChatSDKError("forbidden:chat").toResponse();
      }
    } else {
      const title = await generateTitleFromUserMessage({
        message,
      });

      await saveChat({
        id,
        userId,
        title,
        visibility: selectedVisibilityType,
      });
    }

    // Save user message to database
    await saveMessages({
      messages: [
        {
          chatId: id,
          id: message.id,
          role: "user",
          parts: message.parts,
          attachments: [],
          createdAt: new Date(),
        },
      ],
    });

    // Extract text from message parts
    const textPart = message.parts.find((p) => p.type === "text");
    const query = textPart && "text" in textPart ? textPart.text : "";

    // Extract RAG parameters from request body (with defaults)
    const ragParams = requestBody.ragParams || {};
    const search_db = ragParams.search_db ?? true;
    const use_history = ragParams.use_history ?? true;
    const search_urls = ragParams.search_urls ?? false;
    const n_chunks = ragParams.n_chunks ?? 3;

    // Call FastAPI backend
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    console.log(`[API Route] Calling FastAPI backend at ${backendUrl}/inference`);
    console.log(`[API Route] Query: ${query}`);
    console.log(`[API Route] RAG Params: search_db=${search_db}, use_history=${use_history}, search_urls=${search_urls}, n_chunks=${n_chunks}`);

    // Create AbortController with 10 minute timeout
    const controller = new AbortController();
    let timeoutId: NodeJS.Timeout | null = setTimeout(() => {
      controller.abort();
    }, 600 * 1000); // 10 minutes

    // Function to reset timeout when heartbeat is received
    const resetTimeout = () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      timeoutId = setTimeout(() => {
        controller.abort();
      }, 600 * 1000); // Reset to 10 minutes
      console.log("[API Route] Timeout reset due to heartbeat");
    };

    let backendResponse: Response;
    try {
      backendResponse = await fetch(`${backendUrl}/inference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          user_id: userId,
          session_id: sessionId || `fallback-session-${userId}`,
          search_db: search_db,
          use_history: use_history,
          search_urls: search_urls,
          n_chunks: n_chunks,
        }),
        signal: controller.signal,
      });
    } catch (fetchError) {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      if (fetchError instanceof Error && fetchError.name === 'AbortError') {
        throw new Error('Request timeout: Backend took longer than 10 minutes to respond');
      }
      throw fetchError;
    }

    if (!backendResponse.ok) {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      throw new Error(`Backend error: ${backendResponse.statusText}`);
    }

    console.log("[API Route] Backend response received, streaming to client");

    // Intercept the stream to save the assistant's response
    let assistantResponse = "";
    const stream = backendResponse.body;
    
    if (!stream) {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      throw new Error("No response body from backend");
    }

    // Create a new stream that captures the response text
    const { ReadableStream } = await import("stream/web");
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    
    const interceptedStream = new ReadableStream({
      async start(controller) {
        let isClosed = false;
        
        try {
          while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
              // Save the complete assistant response to database
              if (assistantResponse.trim()) {
                console.log(`[API Route] Saving assistant response: ${assistantResponse.substring(0, 100)}...`);
                try {
                  await saveMessages({
                    messages: [{
                      chatId: id,
                      id: generateUUID(),
                      role: "assistant",
                      parts: [{ type: "text", text: assistantResponse }],
                      attachments: [],
                      createdAt: new Date(),
                    }],
                  });
                } catch (dbError) {
                  console.error("[API Route] Error saving message to database:", dbError);
                  // Continue anyway - don't fail the stream if DB save fails
                }
              }
              
              if (!isClosed) {
                controller.close();
                isClosed = true;
              }
              break;
            }
            
            // Parse chunk for text content before enqueuing
            const chunk = decoder.decode(value, { stream: true });
            
            // Parse SSE events to extract text content and handle heartbeats
            const lines = chunk.split('\n');
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.substring(6));
                  
                  // Handle heartbeat - reset timeout
                  if (data.type === 'heartbeat') {
                    resetTimeout();
                    continue;
                  }
                  
                  // Extract text content
                  if (data.type === 'text-delta' && data.delta) {
                    assistantResponse += data.delta;
                  }
                } catch (e) {
                  // Ignore non-JSON data lines
                }
              }
            }
            
            // Only enqueue if controller is still open
            if (!isClosed) {
              controller.enqueue(value);
            }
          }
        } catch (error) {
          if (timeoutId) {
            clearTimeout(timeoutId);
          }
          console.error("[API Route] Error processing stream:", error);
          if (!isClosed) {
            controller.error(error);
            isClosed = true;
          }
        }
      }
    });

    // Return the intercepted stream
    return new Response(interceptedStream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    const vercelId = request.headers.get("x-vercel-id");

    if (error instanceof ChatSDKError) {
      return error.toResponse();
    }

    console.error("Unhandled error in chat API:", error, { vercelId });
    return new ChatSDKError("offline:chat").toResponse();
  }
}

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url);
  const id = searchParams.get("id");

  if (!id) {
    return new ChatSDKError("bad_request:api").toResponse();
  }

  const session = await auth();

  if (!session?.user) {
    return new ChatSDKError("unauthorized:chat").toResponse();
  }

  const chat = await getChatById({ id });

  if (chat?.userId !== session.user.id) {
    return new ChatSDKError("forbidden:chat").toResponse();
  }

  const deletedChat = await deleteChatById({ id });

  return Response.json(deletedChat, { status: 200 });
}
