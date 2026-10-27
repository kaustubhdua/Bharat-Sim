package org.bharatsim.smokeapp;

import android.app.Activity;
import android.os.Bundle;
import android.os.SystemClock;
import android.graphics.Color;
import android.util.Log;
import android.view.Gravity;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Button;

import java.net.URL;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.io.ByteArrayOutputStream;
import java.io.EOFException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.io.IOException;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLPeerUnverifiedException;

public final class MainActivity extends Activity {
    private static final String TAG = "BharatSimNetworkProbe";
    private static final String PROBE_URL = BuildConfig.PROBE_URL;
    private static final int PROBE_BYTES = 500_000;
    private int probeSequence = 0;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        layout.setPadding(32, 32, 32, 32);
        layout.setBackgroundColor(Color.rgb(245, 248, 242));

        TextView title = new TextView(this);
        title.setText("BharatSim Android smoke test");
        title.setContentDescription("fixture-title");
        title.setTextSize(24);
        title.setTextColor(Color.rgb(30, 70, 45));
        title.setGravity(Gravity.CENTER);

        TextView detail = new TextView(this);
        detail.setText("REAL EMULATOR FIXTURE\nInstall • Launch • Observe • Collect logs");
        detail.setTextSize(16);
        detail.setTextColor(Color.DKGRAY);
        detail.setGravity(Gravity.CENTER);
        detail.setPadding(0, 24, 0, 0);

        TextView status = new TextView(this);
        status.setText("Ready");
        status.setTextSize(16);
        status.setTextColor(Color.rgb(30, 70, 45));
        status.setGravity(Gravity.CENTER);
        status.setContentDescription("journey-status");

        TextView networkStatus = new TextView(this);
        networkStatus.setText("Network probe not run");
        networkStatus.setTextSize(14);
        networkStatus.setTextColor(Color.rgb(30, 70, 45));
        networkStatus.setGravity(Gravity.CENTER);
        networkStatus.setContentDescription("network-probe-status");

        Button action = new Button(this);
        action.setText("Run primary action");
        action.setContentDescription("primary-action");
        action.setOnClickListener(view -> {
            status.setText("Primary action completed");
            final int sequence = ++probeSequence;
            networkStatus.setText("Network probe running");
            new Thread(() -> performNetworkProbe(networkStatus, sequence)).start();
        });

        layout.addView(title);
        layout.addView(detail);
        layout.addView(action);
        layout.addView(status);
        layout.addView(networkStatus);
        setContentView(layout);
    }

    private void performNetworkProbe(TextView target, int sequence) {
        String transport = activeTransport();
        for (int attempt = 1; attempt <= 2; attempt++) {
            long started = SystemClock.elapsedRealtime();
            try {
                ProbeResult result = performPinnedHttpsProbe(PROBE_URL, BuildConfig.PROBE_IP, PROBE_BYTES, started);
                long duration = SystemClock.elapsedRealtime() - started;
                Log.i(TAG, "BHARATSIM_NETWORK_PROBE status=HTTP_" + result.statusCode + " duration_ms=" + duration
                        + " transport=" + transport + " probe=" + sequence
                        + " bytes_read=" + result.bytesRead + " attempts=" + attempt
                        + " endpoint_host=" + new URL(PROBE_URL).getHost() + " endpoint_ip=" + BuildConfig.PROBE_IP);
                final String message = "HTTP " + result.statusCode + " · " + duration + " ms · " + transport
                        + " · probe " + sequence + " · bytes " + result.bytesRead + " · attempts " + attempt;
                runOnUiThread(() -> target.setText(message));
                return;
            } catch (Exception exception) {
                if (exception instanceof IOException && attempt < 2) {
                    Log.w(TAG, "BHARATSIM_NETWORK_PROBE retrying sequence=" + sequence
                            + " attempt=" + attempt + " after=" + exception.getClass().getSimpleName(), exception);
                    try {
                        Thread.sleep(attempt * 1000L);
                    } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();
                        Log.e(TAG, "BHARATSIM_NETWORK_PROBE interrupted sequence=" + sequence, interrupted);
                        runOnUiThread(() -> target.setText("Network probe failed: InterruptedException"));
                        return;
                    }
                    continue;
                }
                Log.e(TAG, "BHARATSIM_NETWORK_PROBE status=ERROR transport=" + transport
                        + " probe=" + sequence + " attempts=" + attempt, exception);
                final String detail = exception.getMessage() == null ? "" : exception.getMessage().replaceAll("[\\r\\n]+", " ").substring(0, Math.min(180, exception.getMessage().replaceAll("[\\r\\n]+", " ").length()));
                final String message = "Network probe failed: " + exception.getClass().getSimpleName() + (detail.isEmpty() ? "" : " · " + detail);
                runOnUiThread(() -> target.setText(message));
                return;
            }
        }
    }

    private static ProbeResult performPinnedHttpsProbe(String urlText, String pinnedIp, int expectedBytes, long startedAt) throws IOException {
        URL url = new URL(urlText);
        if (!"https".equalsIgnoreCase(url.getProtocol()) || pinnedIp.equals("0.0.0.0")) {
            throw new IOException("HTTPS probe URL and pinned IPv4 address are required");
        }
        String host = url.getHost();
        int port = url.getPort() > 0 ? url.getPort() : 443;
        String requestPath = url.getFile().isEmpty() ? "/" : url.getFile();

        // Connect to the CI-resolved numeric IP directly. Layer TLS using the
        // hostname so SNI and the normal certificate hostname verifier remain active.
        Log.i(TAG, "BHARATSIM_NETWORK_PROBE request_started endpoint_host=" + host + " endpoint_ip=" + pinnedIp);
        try (Socket raw = new Socket()) {
            raw.connect(new InetSocketAddress(InetAddress.getByName(pinnedIp), port), 3000);
            try (SSLSocket tls = (SSLSocket) ((SSLSocketFactory) SSLSocketFactory.getDefault())
                    .createSocket(raw, host, port, true)) {
                tls.setSoTimeout(8000);
                tls.startHandshake();
                Log.i(TAG, "BHARATSIM_NETWORK_PROBE tls_handshake_completed endpoint_host=" + host);
                if (!HttpsURLConnection.getDefaultHostnameVerifier().verify(host, tls.getSession())) {
                    throw new SSLPeerUnverifiedException("TLS certificate does not match " + host);
                }

                OutputStream output = tls.getOutputStream();
                String request = "GET " + requestPath + " HTTP/1.1\r\n"
                        + "Host: " + host + "\r\n"
                        + "Connection: close\r\n"
                        + "Accept-Encoding: identity\r\n"
                        + "Cache-Control: no-cache\r\n"
                        + "Range: bytes=0-" + (expectedBytes - 1) + "\r\n\r\n";
                output.write(request.getBytes(StandardCharsets.US_ASCII));
                output.flush();

                InputStream input = tls.getInputStream();
                String statusLine = readHttpLine(input);
                String[] statusParts = statusLine.split(" ", 3);
                if (statusParts.length < 2 || !statusParts[0].startsWith("HTTP/")) {
                    throw new IOException("Malformed HTTP status line: " + statusLine);
                }
                final int statusCode;
                try {
                    statusCode = Integer.parseInt(statusParts[1]);
                } catch (NumberFormatException badStatus) {
                    throw new IOException("Malformed HTTP status code: " + statusLine, badStatus);
                }
                if (statusCode != 200 && statusCode != 206) {
                    throw new IOException("Unexpected HTTP status " + statusCode);
                }

                Log.i(TAG, "BHARATSIM_NETWORK_PROBE response_headers_received status=HTTP_" + statusCode);
                Map<String, String> headers = new HashMap<>();
                String headerLine;
                while (!(headerLine = readHttpLine(input)).isEmpty()) {
                    int colon = headerLine.indexOf(':');
                    if (colon > 0) {
                        headers.put(headerLine.substring(0, colon).trim().toLowerCase(Locale.ROOT),
                                headerLine.substring(colon + 1).trim());
                    }
                }
                String transferEncoding = headers.getOrDefault("transfer-encoding", "").toLowerCase(Locale.ROOT);
                String contentLength = headers.get("content-length");
                if (!transferEncoding.contains("chunked") && contentLength != null) {
                    try {
                        if (Long.parseLong(contentLength) < expectedBytes) {
                            throw new IOException("HTTPS endpoint advertised fewer bytes than requested");
                        }
                    } catch (NumberFormatException badLength) {
                        throw new IOException("Malformed Content-Length header", badLength);
                    }
                }
                int bytesRead = transferEncoding.contains("chunked")
                        ? readChunkedBody(input, expectedBytes, startedAt)
                        : readFixedBody(input, expectedBytes, startedAt);
                if (bytesRead != expectedBytes) {
                    throw new IOException("Expected " + expectedBytes + " probe bytes, received " + bytesRead);
                }
                return new ProbeResult(statusCode, bytesRead);
            }
        }
    }

    private static int readFixedBody(InputStream input, int expectedBytes, long startedAt) throws IOException {
        byte[] buffer = new byte[8192];
        int total = 0;
        while (total < expectedBytes) {
            int count = input.read(buffer, 0, Math.min(buffer.length, expectedBytes - total));
            if (count < 0) break;
            total += count;
            logTransferProgress(total, expectedBytes, startedAt);
        }
        return total;
    }

    private static int readChunkedBody(InputStream input, int expectedBytes, long startedAt) throws IOException {
        int total = 0;
        byte[] buffer = new byte[8192];
        while (total < expectedBytes) {
            String sizeLine = readHttpLine(input);
            int semicolon = sizeLine.indexOf(';');
            String sizeText = (semicolon >= 0 ? sizeLine.substring(0, semicolon) : sizeLine).trim();
            final int chunkSize;
            try {
                chunkSize = Integer.parseInt(sizeText, 16);
            } catch (NumberFormatException badChunk) {
                throw new IOException("Malformed HTTP chunk size: " + sizeLine, badChunk);
            }
            if (chunkSize == 0) {
                while (!readHttpLine(input).isEmpty()) { /* consume trailers */ }
                break;
            }
            int remaining = Math.min(chunkSize, expectedBytes - total);
            int chunkRead = 0;
            while (chunkRead < remaining) {
                int count = input.read(buffer, 0, Math.min(buffer.length, remaining - chunkRead));
                if (count < 0) return total + chunkRead;
                chunkRead += count;
            }
            total += chunkRead;
            logTransferProgress(total, expectedBytes, startedAt);
            if (chunkRead < chunkSize || total == expectedBytes) break;
            if (!readHttpLine(input).isEmpty()) {
                throw new IOException("Malformed HTTP chunk terminator");
            }
        }
        return total;
    }

    private static void logTransferProgress(int bytesRead, int expectedBytes, long startedAt) {
        if (bytesRead < expectedBytes && bytesRead % 250_000 >= 8192) return;
        long elapsedMs = Math.max(1, SystemClock.elapsedRealtime() - startedAt);
        long bytesPerSecond = (long) bytesRead * 1000 / elapsedMs;
        Log.i(TAG, "BHARATSIM_NETWORK_PROBE transfer_progress bytes_read=" + bytesRead
                + " expected_bytes=" + expectedBytes + " elapsed_ms=" + elapsedMs
                + " throughput_bytes_per_second=" + bytesPerSecond);
    }

    private static String readHttpLine(InputStream input) throws IOException {
        ByteArrayOutputStream line = new ByteArrayOutputStream();
        int previous = -1;
        while (true) {
            int current = input.read();
            if (current < 0) {
                if (line.size() == 0) return "";
                throw new EOFException("Unexpected EOF inside HTTP headers");
            }
            if (previous == '\r' && current == '\n') {
                byte[] bytes = line.toByteArray();
                return new String(bytes, 0, Math.max(0, bytes.length - 1), StandardCharsets.US_ASCII);
            }
            line.write(current);
            previous = current;
        }
    }

    private static final class ProbeResult {
        final int statusCode;
        final int bytesRead;

        ProbeResult(int statusCode, int bytesRead) {
            this.statusCode = statusCode;
            this.bytesRead = bytesRead;
        }
    }

    private String activeTransport() {
        ConnectivityManager manager = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        Network active = manager == null ? null : manager.getActiveNetwork();
        NetworkCapabilities caps = manager == null || active == null ? null : manager.getNetworkCapabilities(active);
        if (caps == null) return "UNKNOWN";
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) return "CELLULAR";
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) return "ETHERNET";
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) return "WIFI";
        return "OTHER";
    }
}
