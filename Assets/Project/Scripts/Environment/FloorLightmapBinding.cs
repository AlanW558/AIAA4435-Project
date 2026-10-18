using UnityEngine;
using UnityEngine.Rendering;

namespace IAI.Environment
{
    // The uninterrupted bake surface avoids 600 tiny plank lightmap charts.
    // Its UV2 coordinates match the visible floor's world-space UV2 exactly.
    [ExecuteAlways, DisallowMultipleComponent]
    public sealed class FloorLightmapBinding : MonoBehaviour
    {
        public MeshRenderer bakeSurface;
        public MeshRenderer visibleFloor;
        public bool baking;

        void OnEnable() { Apply(); }
        void Start() { Apply(); }
        void LateUpdate() { Apply(); }

        public void Apply()
        {
            if (!bakeSurface || !visibleFloor || baking) return;
            if (bakeSurface.shadowCastingMode != ShadowCastingMode.ShadowsOnly)
                bakeSurface.shadowCastingMode = ShadowCastingMode.ShadowsOnly;
            if (!visibleFloor.enabled) visibleFloor.enabled = true;
            if (visibleFloor.lightmapIndex != bakeSurface.lightmapIndex)
                visibleFloor.lightmapIndex = bakeSurface.lightmapIndex;
            if (visibleFloor.lightmapScaleOffset != bakeSurface.lightmapScaleOffset)
                visibleFloor.lightmapScaleOffset = bakeSurface.lightmapScaleOffset;
        }
    }
}
