from types import SimpleNamespace

from optitrack_motive.motive_receiver import (
    MotiveReceiver,
    decode_marker_id,
    decode_marker_params,
)


def make_marker_frame():
    mocap_data = SimpleNamespace(
        suffix_data=SimpleNamespace(timestamp=12.5),
        marker_set_data=SimpleNamespace(
            unlabeled_markers=SimpleNamespace(marker_pos_list=[(7.0, 8.0, 9.0)]),
            marker_data_list=[
                SimpleNamespace(
                    model_name=b"left",
                    marker_pos_list=[(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)],
                ),
                SimpleNamespace(
                    model_name=b"all",
                    marker_pos_list=[(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)],
                ),
            ],
        ),
        legacy_other_markers=SimpleNamespace(marker_pos_list=[(0.1, 0.2, 0.3)]),
        labeled_marker_data=SimpleNamespace(
            labeled_marker_list=[
                SimpleNamespace(
                    id_num=(1 << 16) | 4,
                    pos=(0.4, 0.5, 0.6),
                    size=0.012,
                    param=0x06,
                    residual=0.001,
                )
            ]
        ),
        rigid_body_data=SimpleNamespace(
            rigid_body_list=[
                SimpleNamespace(
                    id_num=1,
                    pos=(0.7, 0.8, 0.9),
                    rot=(0.0, 0.0, 0.0, 1.0),
                    mean_error=0.0004,
                    param=1,
                )
            ]
        ),
        asset_data=SimpleNamespace(asset_list=[]),
        skeleton_data=SimpleNamespace(skeleton_list=[]),
    )
    return {"frame_number": 42, "mocap_data": mocap_data}


def test_decode_marker_id_and_params():
    assert decode_marker_id((3 << 16) | 12) == (3, 12)
    assert decode_marker_params(0x07) == {
        "occluded": True,
        "point_cloud_solved": True,
        "model_solved": True,
    }


def test_receiver_exposes_rigid_bodies_and_markers_from_full_frame():
    motive = MotiveReceiver("127.0.0.1", start_process=False)
    motive.process_packet(make_marker_frame())
    frame = motive.get_last()

    assert frame["frame_id"] == 42
    assert motive.get_rigid_body_names(frame) == ["left"]
    assert motive.get_rigid_body("left", frame)["pos"] == (0.7, 0.8, 0.9)
    assert motive.get_marker_sets(frame) == {
        "left": [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)],
        "all": [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)],
    }
    assert motive.get_unlabeled_markers(frame) == [(0.1, 0.2, 0.3)]

    labeled = motive.get_labeled_markers(frame)
    assert labeled == [
        {
            "index": 0,
            "id_num": 65540,
            "model_id": 1,
            "model_name": "left",
            "marker_id": 4,
            "position": (0.4, 0.5, 0.6),
            "size": 0.012,
            "param": 6,
            "residual": 0.001,
            "occluded": False,
            "point_cloud_solved": True,
            "model_solved": True,
        }
    ]
