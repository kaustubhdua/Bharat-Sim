package org.bharatsim.smokeapp;

import org.junit.Test;

import java.io.EOFException;
import java.io.IOException;
import java.net.SocketException;
import java.net.SocketTimeoutException;
import javax.net.ssl.SSLPeerUnverifiedException;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

public class MainActivityTest {

    @Test
    public void testCalculateAttemptBudgetFirstAttempt() {
        // Attempt 1 with plenty of overall time left should use the max attempt timeout (20s)
        long budget = MainActivity.calculateAttemptBudget(1, 45_000L, 20_000);
        assertEquals(20_000L, budget);

        // Attempt 1 with limited overall time reserves 2s for retry attempt
        budget = MainActivity.calculateAttemptBudget(1, 10_000L, 20_000);
        assertEquals(8_000L, budget);

        // Attempt 1 with tight budget maintains minimum 1000ms attempt budget
        budget = MainActivity.calculateAttemptBudget(1, 2_500L, 20_000);
        assertEquals(1_000L, budget);
    }

    @Test
    public void testCalculateAttemptBudgetSecondAttempt() {
        // Attempt 2 uses all remaining overall budget up to max attempt timeout
        long budget = MainActivity.calculateAttemptBudget(2, 15_000L, 20_000);
        assertEquals(15_000L, budget);

        budget = MainActivity.calculateAttemptBudget(2, 25_000L, 20_000);
        assertEquals(20_000L, budget);

        budget = MainActivity.calculateAttemptBudget(2, 5_000L, 20_000);
        assertEquals(5_000L, budget);
    }

    @Test
    public void testRemainingTimeoutMsNominal() throws Exception {
        long now = 10_000L;
        long attemptDeadline = 30_000L; // 20s remaining
        long probeDeadline = 55_000L;   // 45s remaining
        int socketTimeout = 15_000;

        int remaining = MainActivity.remainingTimeoutMs(attemptDeadline, probeDeadline, now, socketTimeout);
        assertEquals(15_000, remaining);
    }

    @Test
    public void testRemainingTimeoutMsBoundedByAttemptDeadline() throws Exception {
        long now = 25_000L;
        long attemptDeadline = 28_000L; // 3s remaining in attempt
        long probeDeadline = 55_000L;   // 30s remaining overall
        int socketTimeout = 15_000;

        int remaining = MainActivity.remainingTimeoutMs(attemptDeadline, probeDeadline, now, socketTimeout);
        assertEquals(3_000, remaining);
    }

    @Test
    public void testRemainingTimeoutMsBoundedByOverallDeadline() throws Exception {
        long now = 52_000L;
        long attemptDeadline = 70_000L; // 18s remaining in attempt
        long probeDeadline = 55_000L;   // 3s remaining overall
        int socketTimeout = 15_000;

        int remaining = MainActivity.remainingTimeoutMs(attemptDeadline, probeDeadline, now, socketTimeout);
        assertEquals(3_000, remaining);
    }

    @Test
    public void testRemainingTimeoutMsThrowsOnAttemptDeadlineExceeded() {
        long now = 31_000L;
        long attemptDeadline = 30_000L; // attempt expired 1s ago
        long probeDeadline = 55_000L;   // overall still active
        int socketTimeout = 15_000;

        try {
            MainActivity.remainingTimeoutMs(attemptDeadline, probeDeadline, now, socketTimeout);
            fail("Expected SocketTimeoutException for attempt deadline exhaustion");
        } catch (IOException e) {
            assertTrue(e instanceof SocketTimeoutException);
            assertTrue(e.getMessage().contains("Probe attempt exceeded"));
        }
    }

    @Test
    public void testRemainingTimeoutMsThrowsOnOverallDeadlineExceeded() {
        long now = 56_000L;
        long attemptDeadline = 60_000L; // attempt technically active
        long probeDeadline = 55_000L;   // overall deadline expired
        int socketTimeout = 15_000;

        try {
            MainActivity.remainingTimeoutMs(attemptDeadline, probeDeadline, now, socketTimeout);
            fail("Expected SocketTimeoutException for overall deadline exhaustion");
        } catch (IOException e) {
            assertTrue(e instanceof SocketTimeoutException);
            assertTrue(e.getMessage().contains("45-second overall deadline"));
        }
    }

    @Test
    public void testIsRetryableException() {
        // Transient network failures qualify for retry
        assertTrue(MainActivity.isRetryableException(new SocketTimeoutException("Read timed out")));
        assertTrue(MainActivity.isRetryableException(new SocketException("Connection reset")));
        assertTrue(MainActivity.isRetryableException(new EOFException("Premature EOF")));
        assertTrue(MainActivity.isRetryableException(new IOException("Broken pipe")));

        // Permanent certificate mismatch must fail immediately without burning retry budget
        assertFalse(MainActivity.isRetryableException(new SSLPeerUnverifiedException("Certificate hostname mismatch")));

        // Runtime errors / programming defects are not retryable
        assertFalse(MainActivity.isRetryableException(new IllegalStateException("Wrong network transport")));
        assertFalse(MainActivity.isRetryableException(new IllegalArgumentException("Invalid URL syntax")));
    }
}
