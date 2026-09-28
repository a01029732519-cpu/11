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

    static String selected(Context c) {
        return c.getSharedPreferences(PREF, 0).getString(KEY, "");
    }

    public static InputStream open(Context c, String path) throws IOException {
        String sel = selected(c);
        if (sel.length() > 0 && path.startsWith("hebi/")) {
            File f = new File(new File(root(c), sel), path.substring(5));
            if (f.isFile()) return new FileInputStream(f);
        }
        return c.getAssets().open(path);
    }

    static String[] list(Context c) {
        ArrayList<String> out = new ArrayList<String>();
        File[] fs = root(c).listFiles();
        if (fs != null) {
            for (File f : fs) {
                if (f.isDirectory() && new File(f, "idle.txt").isFile() && new File(f, "idle.png").isFile()) {
                    out.add(f.getName());
                }
            }
        }
        String[] a = out.toArray(new String[0]);
        Arrays.sort(a);
        return a;
    }

    static String title(Context c, String dir) {
        if (dir == null || dir.length() == 0) return "기본 캐릭터";
        File n = new File(new File(root(c), dir), "name.txt");
        if (n.isFile()) {
            BufferedReader r = null;
            try {
                r = new BufferedReader(new InputStreamReader(new FileInputStream(n), "UTF-8"));
                String s = r.readLine();
                if (s != null && s.trim().length() > 0) return s.trim();
            } catch (Exception e) {
            } finally {
                try { if (r != null) r.close(); } catch (Exception e) { }
            }
        }
        return dir;
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

    static void show(final Activity a, final Button b) {
        final String[] dirs = list(a);
        final String[] names = new String[dirs.length + 1];
        names[0] = title(a, "");
        for (int i = 0; i < dirs.length; i++) names[i + 1] = title(a, dirs[i]);
        String cur = selected(a);
        int checked = 0;
        for (int i = 0; i < dirs.length; i++) if (dirs[i].equals(cur)) checked = i + 1;
        AlertDialog.Builder bd = new AlertDialog.Builder(a);
        bd.setTitle("캐릭터 선택");
        bd.setSingleChoiceItems(names, checked, new DialogInterface.OnClickListener() {
            public void onClick(DialogInterface d, int which) {
                String dir = which == 0 ? "" : dirs[which - 1];
                apply(a, dir);
                b.setText(label(a));
                Toast.makeText(a, names[which] + " 적용!", Toast.LENGTH_SHORT).show();
                d.dismiss();
            }
        });
        if (dirs.length == 0) {
            bd.setMessage(null);
        }
        bd.setNegativeButton("닫기", null);
        bd.show();
        if (dirs.length == 0) {
            Toast.makeText(a, "추가 캐릭터 없음: " + root(a).getAbsolutePath(), Toast.LENGTH_LONG).show();
        }
    }
}
