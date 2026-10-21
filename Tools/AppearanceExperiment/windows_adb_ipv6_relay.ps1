# Run while developing from WSL with Windows adb.exe. Binds only Windows ::1.
# The WSL localhost forwarder serves 127.0.0.1; ADB may choose IPv6 localhost.
param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Net;
using System.Net.Sockets;
using System.Threading.Tasks;
public static class AppearanceLoopbackRelay {
    static async Task Pump(TcpClient source, TcpClient destination) {
        try { await source.GetStream().CopyToAsync(destination.GetStream()); }
        finally { try { destination.Client.Shutdown(SocketShutdown.Send); } catch(SocketException) {} }
    }
    static async Task Relay(TcpClient incoming, int port) {
        using(incoming)
        using(var upstream=new TcpClient(AddressFamily.InterNetwork)) {
            try {
                await upstream.ConnectAsync(IPAddress.Loopback,port);
                // Preserve half-close: a request ending its write side must still receive its response.
                await Task.WhenAll(Pump(incoming,upstream),Pump(upstream,incoming));
            } catch(Exception e) { Console.Error.WriteLine("Relay connection: "+e.GetType().Name); }
        }
    }
    public static void Run(int port) {
        var listener=new TcpListener(IPAddress.IPv6Loopback,port);
        listener.Server.DualMode=false;listener.Start();
        Console.WriteLine("Appearance IPv6 loopback relay ready on ::1:"+port);
        try { while(true) { var incoming=listener.AcceptTcpClient(); var pending=Relay(incoming,port); GC.KeepAlive(pending); } }
        finally { listener.Stop(); }
    }
}
'@
[AppearanceLoopbackRelay]::Run($Port)
