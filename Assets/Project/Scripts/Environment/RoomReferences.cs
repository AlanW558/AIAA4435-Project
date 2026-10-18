using UnityEngine;

namespace IAI.Environment
{
    // Stable anchors for later tutoring, voice and experiment systems.
    public sealed class RoomReferences : MonoBehaviour
    {
        public Transform userSeat;
        public Transform tutorSeat;
        public Transform tutorEye;
        public Transform tableSurface;
        public GameObject tableDecor;
        [Tooltip("Interior clear dimensions in metres: X width, Y height, Z length.")]
        public Vector3 interiorSize = new Vector3(11.5f, 6.75f, 64f/3f);
    }
}
