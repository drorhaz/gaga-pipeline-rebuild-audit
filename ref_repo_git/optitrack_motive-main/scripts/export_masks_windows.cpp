#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "MotiveAPI.h"

namespace {

std::wstring to_wstring(const std::string& value) {
    return std::wstring(value.begin(), value.end());
}

bool write_pgm(const std::wstring& path, int width, int height, const std::vector<unsigned char>& pixels) {
    std::ofstream out(path, std::ios::binary);
    if (!out) {
        return false;
    }
    out << "P5\n" << width << " " << height << "\n255\n";
    out.write(reinterpret_cast<const char*>(pixels.data()), static_cast<std::streamsize>(pixels.size()));
    return static_cast<bool>(out);
}

std::wstring join_path(const std::wstring& dir, const std::wstring& filename) {
    if (dir.empty()) {
        return filename;
    }
    if (dir.back() == L'\\' || dir.back() == L'/') {
        return dir + filename;
    }
    return dir + L"\\" + filename;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "usage: export_masks_windows.exe <calibration.mcal> <out_dir>\n";
        return 2;
    }

    const std::wstring calibration_path = to_wstring(argv[1]);
    const std::wstring out_dir = to_wstring(argv[2]);

    std::cout << "initialize\n";
    const auto init_result = MotiveAPI::Initialize();
    std::cout << "initialize_result=" << static_cast<int>(init_result) << "\n";
    if (init_result != MotiveAPI::kApiResult_Success) {
        return 1;
    }

    int loaded_camera_count = 0;
    const auto load_result = MotiveAPI::LoadCalibration(calibration_path.c_str(), &loaded_camera_count);
    std::cout << "load_result=" << static_cast<int>(load_result) << " cameras=" << loaded_camera_count << "\n";
    if (load_result != MotiveAPI::kApiResult_Success) {
        MotiveAPI::Shutdown();
        return 1;
    }

    const int camera_count = MotiveAPI::CameraCount();
    std::wcout << L"camera_count=" << camera_count << L"\n";

    for (int index = 0; index < camera_count; ++index) {
        int mask_width = 0;
        int mask_height = 0;
        int mask_grid = 0;
        if (!MotiveAPI::CameraMaskInfo(index, mask_width, mask_height, mask_grid)) {
            std::cout << "mask_info_failed index=" << index << "\n";
            continue;
        }

        const int serial = MotiveAPI::CameraSerial(index);
        std::vector<unsigned char> mask_buffer(static_cast<size_t>(mask_width) * static_cast<size_t>(mask_height), 0);
        if (!MotiveAPI::CameraMask(index, mask_buffer.data(), static_cast<int>(mask_buffer.size()))) {
            std::cout << "mask_read_failed serial=" << serial << "\n";
            continue;
        }

        std::wstringstream filename;
        filename << serial << L"_mask_" << mask_width << L"x" << mask_height << L"_g" << mask_grid << L".pgm";
        const auto out_path = join_path(out_dir, filename.str());
        if (!write_pgm(out_path, mask_width, mask_height, mask_buffer)) {
            std::cout << "write_failed serial=" << serial << "\n";
            continue;
        }

        size_t nonzero = 0;
        for (unsigned char pixel : mask_buffer) {
            if (pixel != 0) {
                ++nonzero;
            }
        }
        std::wcout << L"serial=" << serial
                   << L" mask=" << mask_width << L"x" << mask_height
                   << L" grid=" << mask_grid
                   << L" nonzero=" << nonzero
                   << L" file=" << out_path << L"\n";
    }

    MotiveAPI::Shutdown();
    return 0;
}
