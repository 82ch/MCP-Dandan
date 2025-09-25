using System;

namespace CursorProcessTree
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.Write("Enter target process name (e.g., Cursor.exe): ");
            Console.ResetColor();
            string targetProcess = Console.ReadLine()?.Trim() ?? "";

            if (string.IsNullOrEmpty(targetProcess))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[-] No process name entered. Exiting...");
                Console.ResetColor();
                return;
            }

            if (targetProcess.Equals("Cursor.exe", StringComparison.OrdinalIgnoreCase))
            {
                CursorRunner.Run(targetProcess);
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[-] Unsupported process: {targetProcess}");
                Console.ResetColor();
            }
        }
    }
}
