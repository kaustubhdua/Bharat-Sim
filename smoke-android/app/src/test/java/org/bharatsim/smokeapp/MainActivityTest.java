package org.bharatsim.smokeapp;

import org.junit.Test;

import java.io.EOFException;
import java.io.IOException;
import java.net.SocketException;
import java.net.SocketTimeoutException;
import javax.net.ssl.SSLException;
import javax.net.ssl.SSLHandshakeException;
import javax.net.ssl.SSLPeerUnverifiedException;
import javax.net.ssl.SSLProtocolException;

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
    public void testIsRetryableExceptionTransientFailures() {
        // Genuine transient socket and network transport failures qualify for retry
        assertTrue("SocketTimeoutException must be retryable",
                MainActivity.isRetryableException(new SocketTimeoutException("Read timed out")));
        assertTrue("SocketTimeoutException connect timeout must be retryable",
                MainActivity.isRetryableException(new SocketTimeoutException("Connect timed out")));
        assertTrue("SocketException must be retryable",
                MainActivity.isRetryableException(new SocketException("Connection reset by peer")));
        assertTrue("SocketException broken pipe must be retryable",
                MainActivity.isRetryableException(new SocketException("Broken pipe")));
        assertTrue("EOFException must be retryable",
                MainActivity.isRetryableException(new EOFException("Unexpected end of ZLIB input stream")));
    }

    @Test
    public void testIsRetryableExceptionPermanentSecurityAndProtocolFailures() {
        // TLS/SSL certificate, handshake, or protocol configuration failures must not retry
        assertFalse("SSLException must not be retryable",
                MainActivity.isRetryableException(new SSLException("General SSL error")));
        assertFalse("SSLHandshakeException must not be retryable",
                MainActivity.isRetryableException(new SSLHandshakeException("CertPathValidatorException: Trust anchor not found")));
        assertFalse("SSLPeerUnverifiedException must not be retryable",
                MainActivity.isRetryableException(new SSLPeerUnverifiedException("Certificate hostname mismatch")));
        assertFalse("SSLProtocolException must not be retryable",
                MainActivity.isRetryableException(new SSLProtocolException("Cannot negotiate protocol")));
        assertFalse("SocketException wrapping SSLException must not be retryable",
                MainActivity.isRetryableException(new SocketException("Handshake failed", new SSLHandshakeException("Untrusted"))));
        assertFalse("IOException wrapping SSLException must not be retryable",
                MainActivity.isRetryableException(new IOException("TLS error", new SSLException("Internal error"))));

        // Protocol, malformed response, or invalid HTTP status errors must not retry
        assertFalse("Malformed HTTP status line must not be retryable",
                MainActivity.isRetryableException(new IOException("Malformed HTTP status line: NOT_HTTP")));
        assertFalse("Malformed status code must not be retryable",
                MainActivity.isRetryableException(new IOException("Malformed HTTP status code: HTTP/1.1 ABC")));
        assertFalse("Unexpected HTTP status must not be retryable",
                MainActivity.isRetryableException(new IOException("Unexpected HTTP status 500")));
        assertFalse("Oversized headers must not be retryable",
                MainActivity.isRetryableException(new IOException("HTTP response headers exceed configured limits")));
        assertFalse("Undersized advertised content length must not be retryable",
                MainActivity.isRetryableException(new IOException("HTTPS endpoint advertised fewer bytes than requested")));
        assertFalse("Malformed chunk size must not be retryable",
                MainActivity.isRetryableException(new IOException("Malformed HTTP chunk size: ZZ")));
        assertFalse("Malformed chunk terminator must not be retryable",
                MainActivity.isRetryableException(new IOException("Malformed HTTP chunk terminator")));
        assertFalse("Incomplete payload bytes must not be retryable",
                MainActivity.isRetryableException(new IOException("Expected 500000 probe bytes, received 250000")));

        // Programming/configuration defects must not retry
        assertFalse("IllegalStateException must not be retryable",
                MainActivity.isRetryableException(new IllegalStateException("Unsupported transport for emulator-console shaping")));
        assertFalse("IllegalArgumentException must not be retryable",
                MainActivity.isRetryableException(new IllegalArgumentException("HTTPS probe URL and pinned IPv4 address are required")));
        assertFalse("Null exception must not be retryable",
                MainActivity.isRetryableException(null));
    }
}
