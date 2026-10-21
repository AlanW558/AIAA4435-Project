using System;
using System.Collections.Generic;

namespace IAI.Appearance
{
    public enum ScheduleStep { Advance, Pause, Complete }
    public static class AppearanceSchedule
    {
        public static List<TrialRow> Parse(string csv,string participant,StudyTask[] tasks)
        {
            var result=new List<TrialRow>();
            foreach(var line in csv.Split('\n'))
            {
                var c=line.Trim().Split(',');if(c[0]!=participant)continue;
                if(c.Length!=6||!int.TryParse(c[2],out var block)||!int.TryParse(c[3],out var within))
                    throw new ArgumentException("Malformed frozen schedule row.");
                result.Add(new TrialRow{trialId=c[1],block=block,withinBlock=within,condition=c[4],taskId=c[5]});
            }
            if(result.Count!=16)throw new ArgumentException("No complete frozen schedule for this participant.");
            var trials=new HashSet<string>();var taskIds=new HashSet<string>();var conditions=new HashSet<string>();
            for(int i=0;i<result.Count;i++)
            {
                var r=result[i];
                if(r.block!=i/4+1||r.withinBlock!=i%4+1||Array.IndexOf(new[]{"E","A","N","S"},r.condition)<0||
                    string.IsNullOrEmpty(r.trialId)||!trials.Add(r.trialId)||!taskIds.Add(r.taskId)||
                    r.condition!=result[i-i%4].condition||Array.FindIndex(tasks,t=>t.task_id==r.taskId)<0)
                    throw new ArgumentException("Invalid, duplicate or inconsistent frozen schedule row.");
                if(i%4==0)conditions.Add(r.condition);
            }
            if(conditions.Count!=4)throw new ArgumentException("Schedule must include all four conditions.");
            return result;
        }
        public static ScheduleStep Next(List<TrialRow> rows,int index)
        {
            if(index<0||index>=rows.Count)throw new ArgumentOutOfRangeException(nameof(index));
            return index==rows.Count-1?ScheduleStep.Complete:rows[index+1].block!=rows[index].block?ScheduleStep.Pause:ScheduleStep.Advance;
        }
    }
}
