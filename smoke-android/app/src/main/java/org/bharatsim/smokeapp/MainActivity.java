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

import java.net.HttpURLConnection;
import java.net.URL;

public final class MainActivity extends Activity {
    private static final String TAG = "BharatSimNetworkProbe";
    private static final String PROBE_URL = BuildConfig.PROBE_URL;
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
        for (int attempt = 1; attempt <= 4; attempt++) {
            long started = SystemClock.elapsedRealtime();
            int statusCode = -1;
            int bytesRead = 0;
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(PROBE_URL).openConnection();
                connection.setConnectTimeout(15000);
                connection.setReadTimeout(30000);
                connection.setRequestMethod("GET");
                connection.setRequestProperty("Connection", "close");
                connection.setRequestProperty("Accept-Encoding", "identity");
                connection.setRequestProperty("Cache-Control", "no-cache");
                connection.setUseCaches(false);
                statusCode = connection.getResponseCode();
                if (statusCode != 200) {
                    throw new java.io.IOException("Unexpected HTTP status " + statusCode);
                }
                try (java.io.InputStream input = connection.getInputStream()) {
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        bytesRead += count;
                    }
                }
                if (bytesRead != 2000000) {
                    throw new IllegalStateException("Expected 2000000 probe bytes, received " + bytesRead);
                }
                long duration = SystemClock.elapsedRealtime() - started;
                Log.i(TAG, "BHARATSIM_NETWORK_PROBE status=HTTP_200 duration_ms=" + duration
                        + " transport=" + transport + " probe=" + sequence
                        + " bytes_read=" + bytesRead + " attempts=" + attempt);
                final String message = "HTTP 200 · " + duration + " ms · " + transport
                        + " · probe " + sequence + " · bytes " + bytesRead + " · attempts " + attempt;
                runOnUiThread(() -> target.setText(message));
                return;
            } catch (Exception exception) {
                // Public DNS and routing can briefly fail in hosted CI. Retry bounded I/O
                // failures with backoff; keep attempt counts in logcat and UI evidence.
                // Malformed payloads are not retried, and a final failure is never a success.
                if (exception instanceof java.io.IOException && attempt < 4) {
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
                final String message = "Network probe failed: " + exception.getClass().getSimpleName();
                runOnUiThread(() -> target.setText(message));
                return;
            } finally {
                if (connection != null) {
                    connection.disconnect();
                }
            }
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
