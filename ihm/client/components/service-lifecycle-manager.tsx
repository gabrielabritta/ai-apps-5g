"use client";

import { useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import { useSessionId } from "@/lib/session-context";

/**
 * Component that manages service lifecycle by calling turn_on_services
 * when the component mounts (user enters page) and turn_off_services
 * when the component unmounts (user leaves page)
 * Tracks active sessions to only turn off services when no sessions remain
 */
export function ServiceLifecycleManager() {
  const { data: session } = useSession();
  // Get the session ID from context
  const sessionId = useSessionId();
  
  // Flag to track if turn_on_services has been called for this session_id
  const hasTurnedOnRef = useRef<boolean>(false);
  // Flag to prevent multiple calls to turn_off_services
  const hasCalledTurnOffRef = useRef<boolean>(false);

  // Separate effect to handle turn_on_services when session becomes available
  useEffect(() => {
    // Only proceed if we have a session and haven't turned on services yet
    if (!session || hasTurnedOnRef.current) {
      return;
    }

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    const userId = session.user?.id || "00000000-0000-0000-0000-000000000001";

    const turnOnServices = async () => {
      try {
        const response = await fetch(`${backendUrl}/turn_on_services`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            session_id: sessionId,
            user_id: userId,
          }),
        });
        
        if (!response.ok) {
          console.error("Failed to turn on services:", response.statusText);
        } else {
          hasTurnedOnRef.current = true;
          const data = await response.json();
          console.log(`✅ Services turned on - Active sessions: ${data.active_sessions_count}`);
        }
      } catch (error) {
        console.error("Error calling turn_on_services:", error);
      }
    };

    turnOnServices();
  }, [session]); // Only run when session becomes available

  // Store backend URL and session info in refs so they're accessible in cleanup
  const backendUrlRef = useRef<string>(
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"
  );
  const userIdRef = useRef<string>(
    session?.user?.id || "00000000-0000-0000-0000-000000000001"
  );

  // Update userIdRef when session changes
  useEffect(() => {
    if (session?.user?.id) {
      userIdRef.current = session.user.id;
    }
  }, [session]);

  // Main effect for handling page unload events and cleanup
  useEffect(() => {
    const backendUrl = backendUrlRef.current;
    const currentSessionId = sessionId; // Capture sessionId in closure

    // Function to call turn_off_services (with guard to prevent multiple calls)
    const turnOffServices = () => {
      // Prevent multiple calls
      if (hasCalledTurnOffRef.current) {
        return;
      }
      hasCalledTurnOffRef.current = true;
      
      // Use ref to get most current userId
      const requestData = {
        session_id: currentSessionId,
        user_id: userIdRef.current,
      };
      
      try {
        // Use sendBeacon for more reliable delivery when page is closing
        if (navigator.sendBeacon) {
          const blob = new Blob([JSON.stringify(requestData)], {
            type: "application/json",
          });
          navigator.sendBeacon(`${backendUrl}/turn_off_services`, blob);
        } else {
          // Fallback to fetch if sendBeacon is not available
          fetch(`${backendUrl}/turn_off_services`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(requestData),
            keepalive: true, // Keep request alive even if page is closing
          }).catch((error) => {
            console.error("Error calling turn_off_services:", error);
          });
        }
      } catch (error) {
        console.error("Error in turn_off_services:", error);
      }
    };

    // Event handlers for when user leaves the page
    // beforeunload: fires when page is about to be unloaded (close tab, navigate away, etc.)
    const handleBeforeUnload = () => {
      turnOffServices();
    };

    // pagehide: fires when page is being hidden (more reliable than beforeunload)
    const handlePageHide = () => {
      turnOffServices();
    };

    // Add event listeners
    window.addEventListener("beforeunload", handleBeforeUnload);
    window.addEventListener("pagehide", handlePageHide);

    // Cleanup function: called when component unmounts
    return () => {
      // Remove event listeners
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.removeEventListener("pagehide", handlePageHide);
      
      // Only call turn_off_services on unmount if we actually turned on services
      if (hasTurnedOnRef.current && !hasCalledTurnOffRef.current) {
        turnOffServices();
      }
    };
  }, [sessionId]); // Include sessionId as dependency

  // This component doesn't render anything
  return null;
}

