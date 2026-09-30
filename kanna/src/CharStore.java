package com.pastel.aipet;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Toast;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;

/** 외부 캐릭터 폴더(Android/data/<pkg>/files/chars/<이름>/)에서 스프라이트를 읽어오는 도우미. */
public class CharStore {
    private static final String PREF = "charstore";
    private static final String KEY = "sel";

    static File root(Context c) {
        File d = c.getExternalFilesDir(null);
        if (d == null) d = c.getFilesDir();
        return new File(d, "chars");
    }

    static final String HEBI = "hebi";

    static String selected(Context c) {
        String s = c.getSharedPreferences(PREF, 0).getString(KEY, "");
        return HEBI.equals(s) ? s : "";
    }

    public static InputStream open(Context c, String path) throws IOException {
        if (selected(c).length() > 0 && path.startsWith("hebi/")) {
            String rel = path.substring(5);
            try {
                return c.getAssets().open("hebi2/" + rel);
            } catch (IOException e) {
            }
            File f = new File(new File(root(c), HEBI), rel);
            if (f.isFile()) return new FileInputStream(f);
        }
        return c.getAssets().open(path);
    }

    static String[] list(Context c) {
        try {
            String[] a = c.getAssets().list("hebi2");
            if (a != null && a.length > 0) return new String[] { HEBI };
        } catch (Exception e) {
        }
        File d = new File(root(c), HEBI);
        if (new File(d, "idle.txt").isFile() && new File(d, "idle.png").isFile()) {
            return new String[] { HEBI };
        }
        return new String[0];
    }

    static String title(Context c, String dir) {
        return (dir == null || dir.length() == 0) ? "칸나" : "헤비";
    }

    static void apply(Context c, String dir) {
        c.getSharedPreferences(PREF, 0).edit().putString(KEY, dir).commit();
        try {
            Field f = PetService.class.getDeclaredField("hebiImgs");
            f.setAccessible(true);
            f.set(null, null);
        } catch (Throwable t) {
        }
        try {
            if (PetService.get() != null) {
                c.startService(new Intent(c, PetService.class).setAction("com.pastel.aipet.action.RELOAD"));
            }
        } catch (Throwable t) {
        }
    }

    private static Button makeButton(Activity a, String text) {
        try {
            Method m = a.getClass().getDeclaredMethod("button", String.class, boolean.class);
            m.setAccessible(true);
            return (Button) m.invoke(a, text, Boolean.FALSE);
        } catch (Throwable t) {
            Button b = new Button(a);
            b.setText(text);
            return b;
        }
    }

    private static LinearLayout.LayoutParams lp(Activity a, int top) {
        try {
            Method m = a.getClass().getDeclaredMethod("lpTop", int.class);
            m.setAccessible(true);
            return (LinearLayout.LayoutParams) m.invoke(a, top);
        } catch (Throwable t) {
            return new LinearLayout.LayoutParams(-1, -2);
        }
    }

    private static String label(Context c) {
        return "캐릭터 변경  ·  " + title(c, selected(c));
    }

    public static void addUi(final Activity a, LinearLayout parent) {
        try {
            final Button b = makeButton(a, label(a));
            b.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    show(a, b);
                }
            });
            parent.addView(b, lp(a, 10));
        } catch (Throwable t) {
        }
    }

    static boolean hasHebi(Context c) {
        return list(c).length > 0;
    }

    static void show(final Activity a, final Button b) {
        final String[] names = { title(a, ""), title(a, HEBI) };
        int checked = selected(a).length() == 0 ? 0 : 1;
        AlertDialog.Builder bd = new AlertDialog.Builder(a);
        bd.setTitle("캐릭터 선택");
        bd.setSingleChoiceItems(names, checked, new DialogInterface.OnClickListener() {
            public void onClick(DialogInterface d, int which) {
                if (which == 1 && !hasHebi(a)) {
                    Toast.makeText(a, "헤비 그림이 앱에 없어요", Toast.LENGTH_LONG).show();
                    return;
                }
                apply(a, which == 0 ? "" : HEBI);
                b.setText(label(a));
                Toast.makeText(a, names[which] + " 적용!", Toast.LENGTH_SHORT).show();
                d.dismiss();
            }
        });
        bd.setNegativeButton("닫기", null);
        bd.show();
    }
}
